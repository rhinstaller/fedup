/* fedora-system-upgrade.c: upgrade a Fedora system from system-update.target
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
 *       Translation/i18n
 *       Handle RPMCALLBACK_{SCRIPT,CPIO,UNPACK}_ERROR
 *       Do more useful things with RPMCALLBACK_UNINST_{START,STOP}
 *       Use RPMCALLBACK_SCRIPT_{START,STOP} (rpm >= 4.10 only)
 *       Take btrfs/LVM snapshot before upgrade and revert on failure
 *       Clean out packagedir after upgrade
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

/* plymouth */
#include "ply-boot-client.h"

/* File names and locations */
#define UPGRADE_SYMLINK  "/system-update"
#define UPGRADE_FILELIST "package.list"

/* globals */
gchar *packagedir = NULL; /* target of UPGRADE_SYMLINK */
guint numpkgs = 0;        /* number of packages in transaction */

/* commandline options */
static gboolean testing = FALSE;
static gboolean reboot = FALSE;
static gboolean plymouth = FALSE;
static gboolean plymouth_verbose = FALSE;
static gboolean debug = FALSE;
static gchar *root = NULL;

static GOptionEntry options[] =
{
    { "testing", 'n', 0, G_OPTION_ARG_NONE, &testing,
        "Test mode - don't actually install anything", NULL },
    { "root", 'r', 0' G_OPTION_ARG_FILENAME, &root,
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
        command = (char *)cmd;
    retval = g_spawn_command_line_async(command, &error);
    if (!retval) {
        g_warning("command \"%s\" failed: %s", command, error->message);
        g_error_free(error);
    }
    if (command != NULL)
        g_free(command);
    return retval;
}

/******************
 * Plymouth stuff *
 ******************/

#ifdef USE_PLYMOUTH_LIBS
typedef struct
{
    ply_boot_client_t *client = NULL;
    ply_event_loop_t *loop = NULL;
} ply_t;

ply_t ply = { 0 };

/* callback handlers */
void ply_success(void *user_data, ply_boot_client_t *client) {
    ply_event_loop_exit(&ply.loop, TRUE);
}
void ply_failure(void *user_data, ply_boot_client_t *client) {
    ply_event_loop_exit(&ply.loop, FALSE);
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

    if (!ply_boot_client_connect(ply_client, ply_disconnect, ply.loop)) {
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

/* display-message <text> */
gboolean set_plymouth_message(const gchar *message) {
    gboolean retval = TRUE;
    if (!plymouth)
        return TRUE;
    if (message == NULL || *message == '\0')
        retval = call("plymouth hide-message --text=%s", message);
    else
        retval = call("plymouth display-message --text=%s", message);
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

    fullfile = g_strjoin("/", packagedir, file, NULL);
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
rpmts setup_transaction(gchar *root, gchar *files[]) {
    rpmts ts = NULL;
    rpmps probs = NULL;
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
    numpkgs = 0;
    numfiles = g_strv_length(files);
    g_message("found %u packages to install", numfiles);
    g_message("building RPM transaction, one moment...");
    for (file = files; *file && **file; file++) {
        if (add_upgrade(ts, *file) == 0)
            numpkgs++;
        else
            g_warning("couldn't add %s to the transaction", *file);
        /* Ignore errors, just like anaconda did */
    }

    if (numpkgs == 0) {
        g_warning("nothing to upgrade");
        goto fail;
    }

    /* Check transaction */
    g_message("checking RPM transaction...");
    rc = rpmtsCheck(ts);
    probs = rpmtsProblems(ts);
    if (rc || rpmpsNumProblems(probs) > 0) {
        /* FIXME: ignore anything but RPMPROB_{CONFLICT,REQUIRES} */
        rpmpsPrint(NULL, probs);
        rpmpsFree(probs);
        /* once again: ignore errors, following anaconda tradition */
    }

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
    static guint curpkg;
    gchar *pkgfile;
    gchar *nvr = NULL;
    gchar *file = (gchar *)key;
    void *retval = NULL;

    /*
     * The upgrade transaction goes through three phases:
     * prep: TRANS_START, TRANS_PROGRESS, TRANS_STOP
     *     duration: basically negligible
     * install: INST_START, INST_OPEN_FILE, INST_CLOSE_FILE
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
        break;
    case RPMCALLBACK_TRANS_STOP:
        g_debug("trans_stop()");
        curpkg = 0;
        break;

    /* install phase: (open, start, progress..., close) for each package */
    case RPMCALLBACK_INST_START:
        g_debug("inst_start(\"%s\")", file);
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_message("installing %s...", nvr);
        rfree(nvr);
        break;
    case RPMCALLBACK_INST_OPEN_FILE:
        /* NOTE: hdr is NULL (because we haven't opened the file yet) */
        g_debug("inst_open_file(\"%s\")", file);
        pkgfile = g_strjoin("/", packagedir, file, NULL);
        retval = rpmShowProgress(arg, what, amount, total, pkgfile, NULL);
        g_free(pkgfile);
        break;
    case RPMCALLBACK_INST_PROGRESS:
        break;
    case RPMCALLBACK_INST_CLOSE_FILE:   /* Finished installing */
        g_debug("inst_close_file(\"%s\")", file);
        rpmShowProgress(arg, what, amount, total, key, NULL);
        curpkg++;
        percent = (100 * curpkg) / numpkgs;
        if (percent > prevpercent) {
            set_plymouth_percent(percent);
            prevpercent = percent;
        }
        break;

    /* cleanup phase: (start, stop) for each cleanup */
    /* NOTE: file is NULL */
    case RPMCALLBACK_UNINST_START:
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_debug("uninst_start(\"%s\")", nvr);
        rfree(nvr);
        break;
    case RPMCALLBACK_UNINST_STOP:
        nvr = headerGetAsString(hdr, RPMTAG_NVR);
        g_debug("uninst_stop(\"%s\")", nvr);
        rfree(nvr);
        break;

    /* These only exist in rpm >= 4.10 */
#ifdef RPMCALLBACK_SCRIPT_START
    case RPMCALLBACK_SCRIPT_START:
        g_debug("script_start(\"%s\")", file);
        break;
#endif
#ifdef RPMCALLBACK_SCRIPT_STOP
    case RPMCALLBACK_SCRIPT_STOP:
        g_debug("script_stop(\"%s\")", file);
        break;
#endif

    /* errors! oh no! */
    case RPMCALLBACK_SCRIPT_ERROR:
        g_warning("script_error()");
        break;
    /* TODO: RPMCALLBACK_{UNPACK,CPIO}_ERROR */
    default:
        g_debug("unhandled callback number %u", what);
        break;
    }
    return retval;
}

rpmps run_transaction(rpmts ts, gint tsflags) {
    /* probFilter seems odd, but that's what anaconda used to do... */
    gint probFilter = ~RPMPROB_FILTER_DISKSPACE;
    gint rc;
    rpmps probs = NULL;

    rpmtsSetNotifyCallback(ts, rpm_trans_callback, NULL);
    rpmtsSetFlags(ts, rpmtsFlags(ts)|tsflags);
    rc = rpmtsRun(ts, NULL, (rpmprobFilterFlags)probFilter);
    if (rc) {
        probs = rpmtsProblems(ts);
        if (rpmpsNumProblems(probs) == 0) {
            g_warning("RPM transaction finished with errors (code %i)", rc);
            probs = NULL; /* upgrade finished, so basically a success */
        } else {
            g_warning("RPM transaction failed");
        }
    }
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
    context = g_option_context_new("update system from system-update.target");
    g_option_context_add_main_entries(context, options, GETTEXT_PACKAGE);
    if (!g_option_context_parse(context, &argc, &argv, &error))
        g_critical("option_parsing failed: %s", error->message);

    if (g_getenv("UPGRADE_TEST") != NULL)
        testing = TRUE;

    if (testing)
        reboot = FALSE;

#ifdef USE_PLYMOUTH_LIBS
    if (plymouth) {
        if (!plymouth_setup()) {
            g_warning("Disabling plymouth output");
            plymouth = FALSE;
        }
    }
#endif

    if (!plymouth)
        plymouth_verbose = FALSE;

    if (getuid() != 0 || geteuid() != 0)
        g_critical("This program must be run as root.");

    /* do this early to avoid a reboot loop if we crash.. */
    packagedir = g_file_read_link(UPGRADE_SYMLINK, &error);
    if (packagedir == NULL)
        g_critical(error->message);

    g_debug(UPGRADE_SYMLINK " -> %s", packagedir);

    if (!testing)
        g_unlink(UPGRADE_SYMLINK);

    /* read filelist */
    filelist = g_strdup_printf("%s/"UPGRADE_FILELIST, packagedir);
    if (!g_file_get_contents(filelist, &filelist_data, NULL, &error))
        g_critical(error->message);

    g_strchomp(filelist_data);
    files = g_strsplit(filelist_data, "\n", -1);
    g_free(filelist_data);

    /* set up RPM transaction - this takes ~90s (~2% total duration) */
    g_message("preparing for upgrade...");
    ts = setup_transaction(root, files);
    if (ts == NULL)
        goto out;

    /* don't actually run the transaction if we're just testing */
    if (testing)
        tsflags |= RPMTRANS_FLAG_TEST;

    /* LET'S ROCK. 98% of the program runtime is here. */
    g_message("starting upgrade...");
    probs = run_transaction(ts, tsflags);

    /* check for failures */
    if (probs != NULL)
        rpmpsPrint(NULL, probs);
    else
        retval = EXIT_SUCCESS;

    g_debug("cleaning up...");
    /* cleanup */
    rpmpsFree(probs);
    rpmtsFree(ts);
    rpmFreeMacros(NULL);
    rpmFreeRpmrc();

out:
    if (filelist != NULL)
        g_free(filelist);
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
