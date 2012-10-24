/* fedora-system-upgrade.c: upgrade a Fedora system
 *
 * Copyright © 2012 Red Hat Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, see <http://www.gnu.org/licenses/>.
 *
 * Author(s): Will Woods <wwoods@redhat.com>
 *
 * TODO: PLYMOUTH_LIBS stuff is untested/unused
 *       Use RPMCALLBACK_*_PROGRESS to update progress before/between packages
 *       Invoke callback for pre-transaction file scanning
 *       Translation/i18n
 *       Clean out packagedir after upgrade
 *       Take btrfs/LVM snapshot before upgrade and revert on failure
 */

#include <stdlib.h>

#include <glib.h>
#include <glib/gstdio.h>

#include <rpm/rpmlib.h>
#include <rpm/rpmts.h>
#include <rpm/rpmcli.h>     /* rpmShowProgress */

/* i18n */
#define GETTEXT_PACKAGE "fedup"
#include <locale.h>
#include <glib/gi18n.h>

/* File names and locations */
#define UPGRADE_SYMLINK  "system-upgrade"
#define UPGRADE_FILELIST "package.list"

/* How much of the progress bar should each phase use? */
#define TRANS_PERCENT 2    /* FIXME should be 5% so we see initial progress */
#define INSTALL_PERCENT 70
#define ERASE_PERCENT 28

/* globals */
gchar *packagedir = NULL; /* target of UPGRADE_SYMLINK */
guint installcount = 0;   /* number of installs in transaction */
guint erasecount = 0;     /* number of erases in transaction */

/* commandline options */
static gboolean testing = FALSE;
static gboolean reboot = FALSE;
static gboolean plymouth = FALSE;
static gboolean plymouth_verbose = FALSE;
static gboolean debug = FALSE;
static gchar *root = "/";

static GOptionEntry options[] =
{
    { "testing", 'n', 0, G_OPTION_ARG_NONE, &testing,
        "Test mode - don't actually install anything", NULL },
    { "root", 'r', 0, G_OPTION_ARG_FILENAME, &root,
        "Top level directory for upgrade (default: \"/\")", NULL },
    { "reboot", 'b', 0, G_OPTION_ARG_NONE, &reboot,
        "Reboot after upgrade", NULL },
    { "plymouth", 'p', 0, G_OPTION_ARG_NONE, &plymouth,
        "Show progress on plymouth splash screen", NULL },
    { "verbose", 'v', 0, G_OPTION_ARG_NONE, &plymouth_verbose,
        "Show detailed info on plymouth splash screen", NULL },
    { "debug", 'd', 0, G_OPTION_ARG_NONE, &debug,
        "Print copious debugging info", NULL },
    { NULL }
};

/* simple convenience function for calling external binaries */
gboolean call(const gchar *cmd, const gchar *arg) {
    GError *error = NULL;
    gchar *command = NULL;
    gboolean retval;
    if (arg != NULL)
        command = g_strdup_printf(cmd, arg);
    else
        command = g_strdup(cmd);
    retval = g_spawn_command_line_async(command, &error);
    if (!retval) {
        g_warning("failed to spawn \"%s\": %s", command, error->message);
        g_error_free(error);
    }
    g_free(command);
    return retval;
}

/******************
 * Plymouth stuff *
 ******************/

#ifdef USE_PLYMOUTH_LIBS
#include "ply-boot-client.h"

typedef struct
{
    ply_boot_client_t *client;
    ply_event_loop_t *loop;
} ply_t;

ply_t ply = { 0 };

/* callback handlers */
void ply_success(void *user_data, ply_boot_client_t *client) {
    ply_event_loop_exit(ply.loop, TRUE);
}
void ply_failure(void *user_data, ply_boot_client_t *client) {
    ply_event_loop_exit(ply.loop, FALSE);
}
void ply_disconnect(void *unused) {
    g_warning("unexpectedly disconnected from plymouth");
    plymouth = FALSE;
    ply_event_loop_exit(ply.loop, FALSE);
    /* TODO: attempt reconnect? */
}

/* display-message <text> */
gboolean set_plymouth_message(const gchar *message) {
    if (!plymouth)
        return TRUE;
    if (message == NULL || *message == '\0')
        ply_boot_client_tell_daemon_to_hide_message(ply.client, message,
                                                ply_success, ply_failure, &ply);
    else
        ply_boot_client_tell_daemon_to_display_message(ply.client, message,
                                                ply_success, ply_failure, &ply);
    return ply_event_loop_run(ply.loop);
}

/* system-update <progress-percent> */
gboolean set_plymouth_percent(const guint percent) {
    gchar *percentstr;
    if (!plymouth)
        return TRUE;
    percentstr = g_strdup_printf("%u", percent);
    ply_boot_client_system_update(ply.client, percentstr,
                                  ply_success, ply_failure, &ply);
    g_free(percentstr); /* this is OK - plymouth strdups percentstr */
    return ply_event_loop_run(ply.loop);
}

gboolean plymouth_setup(void) {
    gboolean plymouth_ok = FALSE;

    ply.loop = ply_event_loop_new();
    ply.client = ply_boot_client_new();

    if (!ply_boot_client_connect(ply.client,
            (ply_boot_client_disconnect_handler_t) ply_disconnect,
            NULL)) {
        g_warning("Couldn't connect to plymouth");
        goto out;
    }

    ply_boot_client_attach_to_event_loop(ply.client, ply.loop);
    ply_boot_client_ping_daemon(ply.client, ply_success, ply_failure, &ply);
    plymouth_ok = ply_event_loop_run(ply.loop);

out:
    if (!plymouth_ok) {
        ply_boot_client_free(ply.client);
        ply_event_loop_free(ply.loop);
        ply.client = NULL;
        ply.loop = NULL;
    }
    return plymouth_ok;
}

#else /* !USE_PLYMOUTH_LIBS */

/* just see if plymouth is alive */
gboolean plymouth_setup(void) {
    return call("plymouth --ping", NULL);
}

/* display-message <text> */
gboolean set_plymouth_message(const gchar *message) {
    gboolean retval = TRUE;
    if (!plymouth)
        return TRUE;
    if (message == NULL || *message == '\0')
        retval = call("plymouth hide-message --text=\"%s\"", message);
    else
        retval = call("plymouth display-message --text=\"%s\"", message);
    return retval;
}

/* system-update <progress-percent> */
gboolean set_plymouth_percent(const guint percent) {
    gboolean retval = TRUE;
    gchar *percentstr;
    if (!plymouth)
        return TRUE;
    percentstr = g_strdup_printf("%u", percent);
    retval = call("plymouth system-update --progress=%s", percentstr);
    g_free(percentstr);
    return retval;
}

#endif /* USE_PLYMOUTH_LIBS */

/*************************
 * RPM transaction stuff *
 *************************/

/* Add the given file to the given RPM transaction */
int add_upgrade(rpmts ts, gchar *file) {
    FD_t fd = NULL;
    Header hdr = NULL;
    gchar *fullfile = NULL;
    gint rc = 1;

    fullfile = g_build_filename(packagedir, file, NULL);
    if (fullfile == NULL) {
        g_warning("failed to allocate memory");
        goto out;
    }

    /* open package file */
    fd = Fopen(fullfile, "r.ufdio");
    if (fd == NULL) {
        g_warning("failed to open file %s", fullfile);
        goto out;
    }

    /* get the RPM header */
    rc = rpmReadPackageFile(ts, fd, fullfile, &hdr);
    if (rc != RPMRC_OK) {
        g_warning("unable to read package %s", file);
        goto out;
    }

    /* add it to the transaction.
     * last two args are 'upgrade' and 'relocs' */
    rc = rpmtsAddInstallElement(ts, hdr, file, 1, NULL);
    g_debug("added %s to transaction", file);
    if (rc) {
        g_warning("failed to add %s to transaction", file);
        goto out;
    }

    rc = 0; /* success */

out:
    if (fd != NULL)
        Fclose(fd);
    if (hdr != NULL)
        headerFree(hdr);
    if (fullfile != NULL)
        g_free(fullfile);
    return rc;
}

/* Set up the RPM transaction using the list of packages to install */
rpmts setup_transaction(gchar *files[]) {
    rpmts ts = NULL;
    rpmps probs = NULL;
    rpmtsi tsi = NULL;
    rpmte te = NULL;
    gchar **file = NULL;
    gint rc = 1;
    guint numfiles = 0;

    /* Read config and initialize transaction */
    rpmReadConfigFiles(NULL, NULL);
    ts = rpmtsCreate();
    rpmtsSetRootDir(ts, root);

    /* Disable signature checking, as anaconda did */
    rpmtsSetVSFlags(ts, rpmtsVSFlags(ts) | _RPMVSF_NOSIGNATURES);


    /* Populate the transaction */
    numfiles = g_strv_length(files);
    g_message("found %u packages to install", numfiles);
    g_message("building RPM transaction, one moment...");
    for (file = files; *file && **file; file++) {
        if (add_upgrade(ts, *file))
            g_warning("couldn't add %s to the transaction", *file);
        /* Ignore errors, just like anaconda did */
    }

    /* get some transaction info */
    tsi = rpmtsiInit(ts);
    while ((te = rpmtsiNext(tsi, 0)) != NULL) {
        if (rpmteType(te) == TR_ADDED)
            installcount++;
        else
            erasecount++;
    }
    g_message("%u packages to install, %u to erase", installcount, erasecount);
    tsi = rpmtsiFree(tsi);

    if (installcount == 0) {
        g_warning("nothing to upgrade");
        goto fail;
    }

    /* Check transaction */
    g_message("checking RPM transaction...");
    rc = rpmtsCheck(ts);
    if (rc) {
        g_warning("transaction check failed (couldn't open rpmdb)");
        goto fail;
    }

    /* Log any transaction problems encountered */
    probs = rpmtsProblems(ts);
    if (probs != NULL) {
        g_message("non-fatal problems with RPM transaction:");
        /* FIXME: ignore anything but RPMPROB_{CONFLICT,REQUIRES} */
        rpmpsPrint(stdout, probs);
        rpmpsFree(probs);
    }
    /* Continue on, ignoring errors, as is anaconda tradition... */

    /* Order transaction */
    rc = rpmtsOrder(ts);
    if (rc > 0) {
        /* this should never happen */
        g_warning("rpm transaction ordering failed");
        goto fail;
    }

    /* Clean transaction */
    rpmtsClean(ts);

    /* All ready! Return the ts. */
    return ts;

fail:
    rpmtsFree(ts);
    return NULL;
}

/* tag -> string helper (copied from rpm/lib/rpmscript.c) */
const char *script_type(rpmTagVal tag) {
    switch (tag) {
    case RPMTAG_PRETRANS:       return "%pretrans";
    case RPMTAG_TRIGGERPREIN:   return "%triggerprein";
    case RPMTAG_PREIN:          return "%pre";
    case RPMTAG_POSTIN:         return "%post";
    case RPMTAG_TRIGGERIN:      return "%triggerin";
    case RPMTAG_TRIGGERUN:      return "%triggerun";
    case RPMTAG_PREUN:          return "%preun";
    case RPMTAG_POSTUN:         return "%postun";
    case RPMTAG_POSTTRANS:      return "%posttrans";
    case RPMTAG_TRIGGERPOSTUN:  return "%triggerpostun";
    case RPMTAG_VERIFYSCRIPT:   return "%verify";
    default: break;
    }
    return "%unknownscript";
}

/* Transaction callback handler, to display RPM progress */
void *rpm_trans_callback(const void *arg,
                         const rpmCallbackType what,
                         const rpm_loff_t amount,
                         const rpm_loff_t total,
                         fnpyKey key,
                         void *data)
{
    Header hdr = (Header) arg;
    static guint percent;
    static guint prevpercent;
    static guint installed = 0;
    static guint erased = 0;
    gchar *pkgfile;
    static guint cb_seen = 0;
    gchar *nvr = NULL;
    gchar *file = (gchar *)key;
    void *retval = NULL;

    /*
     * The upgrade transaction goes through three phases:
     * prep: TRANS_START, TRANS_PROGRESS, TRANS_STOP
     *     duration: basically negligible
     * install: INST_START, INST_OPEN_FILE, INST_STOP, INST_CLOSE_FILE
     *     duration: very roughly 2/3 the transaction
     * cleanup:  UNINST_START, UNINST_STOP
     *     duration: the remainder
     */

    switch (what) {

    /* prep phase: (start, progress..., stop), just once */
    case RPMCALLBACK_TRANS_START:
        g_debug("trans_start()");
        g_message("preparing RPM transaction, one moment...");
        break;
    case RPMCALLBACK_TRANS_PROGRESS:
        /* FIXME: track progress up to TRANS_PERCENT */
        break;
    case RPMCALLBACK_TRANS_STOP:
        g_debug("trans_stop()");
        break;

    /* install phase: (open, start, progress..., stop, close) for each pkg */
    case RPMCALLBACK_INST_OPEN_FILE:
        /* NOTE: hdr is NULL (because we haven't opened the file yet) */
        g_debug("inst_open_file(\"%s\")", file);
        pkgfile = g_build_filename(packagedir, file, NULL);
        retval = rpmShowProgress(arg, what, amount, total, pkgfile, NULL);
        g_free(pkgfile);
        break;
    case RPMCALLBACK_INST_START:
        g_debug("inst_start(\"%s\")", file);
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_message("[%u/%u] (%u%%) installing %s...",
                  installed+1, installcount, percent, nvr);
        rfree(nvr);
        break;
    case RPMCALLBACK_INST_PROGRESS:
        break;
    case RPMCALLBACK_INST_STOP:
        g_debug("inst_stop(\"%s\")", file);
        break;
    case RPMCALLBACK_INST_CLOSE_FILE:
        g_debug("inst_close_file(\"%s\")", file);
        rpmShowProgress(arg, what, amount, total, key, NULL);
        /* NOTE: we do this here 'cuz test transactions don't do start/stop */
        installed++;
        percent = TRANS_PERCENT + \
                    ((INSTALL_PERCENT*installed) / installcount);
        if (percent > prevpercent) {
            set_plymouth_percent(percent);
            prevpercent = percent;
        }
        break;

    /* cleanup phase: (start, progress..., stop) for each cleanup */
    /* NOTE: file is NULL */
    case RPMCALLBACK_UNINST_START:
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_debug("uninst_start(\"%s\")", nvr);
        g_message("[%u/%u] (%u%%) cleaning %s...",
                  erased+1, erasecount, percent, nvr);
        rfree(nvr);
        break;
    case RPMCALLBACK_UNINST_PROGRESS:
        break;
    case RPMCALLBACK_UNINST_STOP:
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_debug("uninst_stop(\"%s\")", nvr);
        erased++;
        percent = TRANS_PERCENT + INSTALL_PERCENT + \
                    ((ERASE_PERCENT*erased) / erasecount);
        if (percent > prevpercent) {
            set_plymouth_percent(percent);
            prevpercent = percent;
        }
        rfree(nvr);
        break;

    /*
     * SCRIPT CALLBACKS (rpm >= 4.10) - happen all throughout the transaction.
     * hdr and file/key are both usable.
     * amount is the script type (RPMTAG_PREIN, RPMTAG_POSTIN, ...)
     * total is the script exit value (see comments below)
     * Ordering is: START; STOP; ERROR if script retval != RPMRC_OK
     */
    case RPMCALLBACK_SCRIPT_START:
        /* no exit value here, obviously */
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_debug("%s_start(\"%s\")", script_type(amount), nvr);
        /* NOTE: %posttrans usually takes a while - report progress! */
        if (amount == RPMTAG_POSTTRANS)
            g_message("running %s script for %s", script_type(amount), nvr);
        break;
    case RPMCALLBACK_SCRIPT_STOP:
        /* RPMRC_OK:        scriptlet succeeded
         * RPMRC_NOTFOUND:  scriptlet failed non-fatally (warning)
         * other:           scriptlet failed, preventing install/erase
         *                  (this only happens for PREIN/PREUN/PRETRANS) */
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_debug("%s_stop(\"%s\")", script_type(amount), nvr);
        break;
    case RPMCALLBACK_SCRIPT_ERROR:
        /* RPMRC_OK:        scriptlet failed non-fatally (warning)
         * other:           scriptlet failed, preventing install/erase */
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_debug("%s_error(\"%s\"): %u", script_type(amount), nvr, total);
        g_warning("%s %s scriptlet failure in %s (exit code %u)",
            total == RPMRC_OK ? "non-fatal" : "fatal",
            script_type(amount), nvr, total);
        /* TODO: show the script contents? */
        break;

    /* these are probably fatal, and there's not much we can do about it..
     * the RPM test transaction should catch nearly all of these well before
     * we end up here, though. */
    case RPMCALLBACK_UNPACK_ERROR:
    case RPMCALLBACK_CPIO_ERROR:
        g_warning("error unpacking %s! file may be corrupt!", file);
        break;

    default:
        if (!(what & cb_seen)) {
            g_debug("unhandled callback number %u", what);
            cb_seen |= what;
        }
        break;
    }
    return retval;
}

rpmps run_transaction(rpmts ts, gint tsflags) {
    /* probFilter seems odd, but that's what anaconda used to do... */
    gint probFilter = ~RPMPROB_FILTER_DISKSPACE;
    gint rc;
    rpmps probs = NULL;

    /* send scriptlet stderr somewhere useful. */
    rpmtsSetScriptFd(ts, fdDup(STDOUT_FILENO));
    /* rpmSetVerbosity(RPMLOG_INFO) would give us script stdout, if we cared */

    rpmtsSetNotifyCallback(ts, rpm_trans_callback, NULL);
    rpmtsSetFlags(ts, rpmtsFlags(ts)|tsflags);
    rc = rpmtsRun(ts, NULL, (rpmprobFilterFlags)probFilter);
    g_debug("transaction finished");
    if (rc > 0)
        probs = rpmtsProblems(ts);
    if (rc < 0)
        g_message("Upgrade finished with non-fatal errors.");
        /* AFAICT probs would be empty here, so that's all we can say.. */
    return probs;
}

/*******************
 * logging handler *
 *******************/

void log_handler(const gchar *log_domain, GLogLevelFlags log_level,
                 const gchar *message, gpointer user_data)
{
    switch (log_level & G_LOG_LEVEL_MASK) {
        /* NOTE: ERROR is still handled by the default handler. */
        case G_LOG_LEVEL_CRITICAL:
            g_printf("ERROR: %s\n", message);
            exit(1);
            break;
        case G_LOG_LEVEL_WARNING:
            /* TODO: once the journal problems are fixed, send warnings and
             *       scriptlet stderr to stderr.
             * see https://bugzilla.redhat.com/show_bug.cgi?id=869061 */
            g_printf("Warning: %s\n", message);
            break;
        case G_LOG_LEVEL_MESSAGE:
            g_printf("%s\n", message);
            if (plymouth_verbose)
                set_plymouth_message(message);
            break;
        case G_LOG_LEVEL_INFO:
            if (debug)
                g_printf("%s\n", message);
            break;
        case G_LOG_LEVEL_DEBUG:
            if (debug)
                g_printf("DEBUG: %s\n", message);
            break;
    }
    fflush(stdout);
}

/****************
 * main program *
 ****************/

/* Total runtime for my test system (F17->F18) is ~70m. */
int main(int argc, char* argv[]) {
    gchar *filelist = NULL;
    gchar *filelist_data = NULL;
    gchar *symlink = NULL;
    gchar *link_target = NULL;
    gchar *origroot = NULL;
    gchar **files = NULL;
    GError *error = NULL;
    rpmts ts = NULL;
    rpmps probs = NULL;
    gint tsflags = RPMTRANS_FLAG_NONE;
    gint retval = EXIT_FAILURE;
    GOptionContext *context;

    /* setup */
    setlocale(LC_ALL, "");
    /* g_type_init(); */
    g_log_set_handler(NULL, G_LOG_LEVEL_MASK, log_handler, NULL);


    /* parse commandline */
    context = g_option_context_new("upgrade a Fedora system");
    g_option_context_add_main_entries(context, options, GETTEXT_PACKAGE);
    if (!g_option_context_parse(context, &argc, &argv, &error))
        g_critical("option_parsing failed: %s", error->message);

    if (getuid() != 0 || geteuid() != 0)
        g_critical("This program must be run as root.");

    if (g_getenv("UPGRADE_TEST") != NULL)
        testing = TRUE;

    if (testing)
        reboot = FALSE;

    if (plymouth) {
        if (!plymouth_setup()) {
            g_warning("Disabling plymouth output");
            plymouth = FALSE;
        }
    }

    if (!plymouth)
        plymouth_verbose = FALSE;

    if (!g_path_is_absolute(root)) {
        origroot = root;
        root = realpath(origroot, NULL);
        g_debug("root is \"%s\"", root);
    }
    if ((root == NULL) || (!g_file_test(root, G_FILE_TEST_IS_DIR)))
        g_critical("--root: \"%s\" is not a directory", origroot);


    /* read the magic symlink */
    symlink = g_build_filename(root, UPGRADE_SYMLINK, NULL);

    link_target = g_file_read_link(symlink, &error);
    if (link_target == NULL)
        g_critical(error->message);

    packagedir = g_build_filename(root, link_target, NULL);
    g_debug("%s -> %s", symlink, packagedir);

    /* delete the symlink immediately (avoid reboot loop if we crash..) */
    if (!testing)
        g_unlink(symlink);
    g_free(symlink);
    g_free(link_target);


    /* read filelist from packagedir */
    filelist = g_build_filename(packagedir, UPGRADE_FILELIST, NULL);
    if (!g_file_get_contents(filelist, &filelist_data, NULL, &error))
        g_critical(error->message);

    /* parse the data into a list of files */
    g_strchomp(filelist_data);
    files = g_strsplit(filelist_data, "\n", -1);

    g_free(filelist);
    g_free(filelist_data);


    /* set up RPM transaction - this takes ~90s (~2% total duration) */
    g_message("preparing for upgrade...");
    ts = setup_transaction(files);
    if (ts == NULL)
        goto out;

    /* don't actually run the transaction if we're just testing */
    if (testing)
        tsflags |= RPMTRANS_FLAG_TEST;


    /* LET'S ROCK. 98% of the program runtime is here. */
    g_message("starting upgrade...");
    probs = run_transaction(ts, tsflags);


    /* check for failures */
    if (probs != NULL) {
        g_message("ERROR: upgrade failed due to the following problems:");
        rpmpsPrint(stdout, probs);
    } else {
        g_message("upgrade finished.");
        retval = EXIT_SUCCESS;
    }

    /* TODO: plymouth_finish() (disconnect and/or force progress to 100%) */

    /* cleanup */
    g_debug("cleaning up...");
    rpmpsFree(probs);
    rpmtsFree(ts);
    rpmFreeMacros(NULL);
    rpmFreeRpmrc();

out:
    if (packagedir != NULL)
        g_free(packagedir);
    if (files != NULL)
        g_strfreev(files);
    if (reboot)
        call("/usr/bin/systemctl --fail --no-block reboot", NULL);
    else
        g_debug("skipping reboot");
    return retval;
}
