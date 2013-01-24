#!/usr/bin/python
#
# fedup.py - commandline frontend for fedup, the Fedora Upgrader.
#
# Copyright (C) 2012 Red Hat Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Will Woods <wwoods@redhat.com>

import os, sys, time
import argparse, platform
from subprocess import call

from fedup.download import FedupDownloader, YumBaseError
from fedup.download import prep_upgrade, prep_boot, setup_media_mount
from fedup.download import reset_boot, remove_boot, remove_cache, misc_cleanup
from fedup.upgrade import FedupUpgrade, TransactionError
from fedup import textoutput as output

import logging, fedup.logutils, fedup.media
log = logging.getLogger("fedup")
def message(m):
    print m
    log.info(m)

from fedup import _, kernelpath, initrdpath

def setup_downloader(version, instrepo=None, cacheonly=False, repos=[]):
    log.debug("setup_downloader(version=%s, repos=%s)", version, repos)
    f = FedupDownloader(version=version, cacheonly=cacheonly)
    f.instrepoid = instrepo
    repo_cb = output.RepoCallback()
    repo_prog = output.RepoProgress(fo=sys.stderr)
    disabled_repos = f.setup_repos(callback=repo_cb,
                                   progressbar=repo_prog,
                                   repos=repos)
    disabled_repos = filter(lambda id: id != f.instrepoid, disabled_repos)
    if disabled_repos:
        print _("No upgrade available for the following repos") + ": " + \
                " ".join(disabled_repos)
        log.info("disabled repos: " + " ".join(disabled_repos))
    return f

def download_packages(f):
    updates = f.build_update_transaction(callback=output.DepsolveCallback(f))
    # check for empty upgrade transaction
    if not updates:
        print _('Your system is already upgraded!')
        print _('Finished. Nothing to do.')
        raise SystemExit(0)
    # clean out any unneeded packages from the cache
    f.clean_cache(keepfiles=(p.localPkg() for p in updates))
    # download packages
    f.download_packages(updates, callback=output.DownloadCallback())

    return updates

def transaction_test(pkgs):
    print _("testing upgrade transaction")
    pkgfiles = set(po.localPkg() for po in pkgs)
    fu = FedupUpgrade()
    fu.setup_transaction(pkgfiles=pkgfiles)
    fu.test_transaction(callback=output.TransactionCallback(numpkgs=len(pkgfiles)))

def reboot():
    call(['systemctl', 'reboot'])

## argument parsing stuff ##
# TODO: move to fedup/parse_args.py so it can be shared with GUI?

class RepoAction(argparse.Action):
    '''Hold a list of repo actions so we can apply them in the order given.'''
    def __call__(self, parser, namespace, value, opt=None):
        curval = getattr(namespace, self.dest, [])
        action = ''
        if opt.startswith('--enable'):
            action = 'enable'
        elif opt.startswith('--disable'):
            action = 'disable'
        elif opt.startswith('--repo') or opt.startswith('--addrepo'):
            action = 'add'
        curval.append((action, value))
        setattr(namespace, self.dest, curval)

# check the argument to '--device' to see if it refers to install media
def device_or_mnt(arg):
    if arg == 'auto':
        media = fedup.media.find()
    else:
        media = [m for m in fedup.media.find() if arg in (m.dev, m.mnt)]

    if len(media) == 1:
        return media.pop()

    if not media:
        msg = _("no install media found - please mount install media first")
        if arg != 'auto':
            msg = "%s: %s" % (arg, msg)
    else:
        devs = ", ".join(m.dev for m in media)
        msg = _("multiple devices found. please choose one of (%s)") % devs
    raise argparse.ArgumentTypeError(msg)

# check the argument to '--iso' to make sure it's somewhere we can use it
def isofile(arg):
    if not os.path.exists(arg):
        raise argparse.ArgumentTypeError(_("File not found: %s") % arg)
    if not os.path.isfile(arg):
        raise argparse.ArgumentTypeError(_("Not a regular file: %s") % arg)
    if not fedup.media.isiso(arg):
        raise argparse.ArgumentTypeError(_("Not an ISO 9660 image: %s") % arg)
    if any(arg.startswith(d.mnt) for d in fedup.media.removable()):
        raise argparse.ArgumentTypeError(_("ISO image on removable media\n"
            "Sorry, but this isn't supported yet.\n"
            "Copy the image to your hard drive or burn it to a disk."))
    return arg

def VERSION(arg):
    if arg.lower() == 'rawhide':
        return 'rawhide'

    distro, version, id = platform.linux_distribution()
    version = int(version)

    if int(arg) >= version:
        return arg
    else:
        msg = _("version must be greater than %i") % version
        raise argparse.ArgumentTypeError(msg)

def parse_args():
    p = argparse.ArgumentParser(
        description=_('Prepare system for upgrade.'),
        # Translators: This is the CLI's "usage:" string
        usage=_('%(prog)s SOURCE [options]'),
    )

    p.add_argument('-v', '--verbose', action='store_const', dest='loglevel',
        const=logging.INFO, help=_('print more info'))
    p.add_argument('-d', '--debug', action='store_const', dest='loglevel',
        const=logging.DEBUG, help=_('print lots of debugging info'))
    p.set_defaults(loglevel=logging.WARNING)

    p.add_argument('--debuglog', default='/var/log/fedup.log',
        help=_('write lots of debugging output to the given file'))

    # FOR DEBUGGING ONLY
    p.add_argument('--skippkgs', action='store_true', default=False,
        help=argparse.SUPPRESS)
    p.add_argument('--skipkernel', action='store_true', default=False,
        help=argparse.SUPPRESS)
    p.add_argument('-C', '--cacheonly', action='store_true', default=False,
        help=argparse.SUPPRESS)
    p.add_argument('--expire-cache', action='store_true', default=False,
        help=argparse.SUPPRESS)
    p.add_argument('--clean-metadata', action='store_true', default=False,
        help=argparse.SUPPRESS)
    p.add_argument('--skipbootloader', action='store_true', default=False,
        help=argparse.SUPPRESS)

    p.add_argument('--reboot', action='store_true', default=False,
        help=_('automatically reboot to start the upgrade when ready'))

    req = p.add_argument_group('SOURCE',
                               _('Location to search for upgrade data.'))
    req.add_argument('--device', metavar='DEV', nargs='?',
        type=device_or_mnt, const='auto',
        help=_('device or mountpoint. default: check mounted devices'))
    req.add_argument('--iso', type=isofile,
        help=_('installation image file'))
    # Translators: This is for '--network [VERSION]' in --help output
    req.add_argument('--network', metavar=_('VERSION'), type=VERSION,
        help=_('online repos matching VERSION (a number or "rawhide")'))

    net = p.add_argument_group(_('additional options for --network'))
    net.add_argument('--enablerepo', metavar='REPOID', action=RepoAction,
        dest='repos', help=_('enable one or more repos (wildcards allowed)'))
    net.add_argument('--disablerepo', metavar='REPOID', action=RepoAction,
        dest='repos', help=_('disable one or more repos (wildcards allowed)'))
    net.add_argument('--repourl', metavar='REPOID=URL', action=RepoAction,
        dest='repos', help=argparse.SUPPRESS)
    net.add_argument('--addrepo', metavar='REPOID=[@]URL',
        action=RepoAction, dest='repos',
        help=_('add the repo at URL (@URL for mirrorlist)'))
    net.add_argument('--instrepo', metavar='REPOID', type=str,
        help=_('get upgrader boot images from REPOID (default: auto)'))
    p.set_defaults(repos=[])

    clean = p.add_argument_group(_('cleanup commands'))

    clean.add_argument('--resetbootloader', action='store_const',
        dest='clean', const='bootloader', default=None,
        help=_('remove any modifications made to bootloader'))
    clean.add_argument('--clean', action='store_const', const='all',
        help=_('clean up everything written by fedup'))

    args = p.parse_args()

    if not (args.network or args.device or args.iso or args.clean):
        p.error(_('SOURCE is required (--network, --device, --iso)'))

    # allow --instrepo URL as shorthand for --repourl REPO=URL --instrepo REPO
    if args.instrepo and '://' in args.instrepo:
        args.repos.append(('add', 'cmdline-instrepo=%s' % args.instrepo))
        args.instrepo = 'cmdline-instrepo'

    # treat --device like --repo REPO=file://$MOUNTPOINT
    if args.device:
        args.repos.append(('add', 'fedupdevice=file://%s' % args.device.mnt))
        args.instrepo = 'fedupdevice'
    elif args.iso:
        args.device = fedup.media.loopmount(args.iso)
        args.repos.append(('add', 'fedupiso=file://%s' % args.device.mnt))
        args.instrepo = 'fedupiso'

    if args.clean:
        args.resetbootloader = True

    return args

def do_cleanup(args):
    if not args.skipbootloader:
        print "resetting bootloader config"
        reset_boot()
    if args.clean == 'bootloader':
        return
    if not args.skipkernel:
        print "removing boot images"
        remove_boot()
    if not args.skippkgs:
        print "removing downloaded packages"
        remove_cache()
    print "removing miscellaneous files"
    misc_cleanup()

def main(args):
    if args.clean:
        do_cleanup(args)
        return

    # Get our packages set up where we can use 'em
    print _("setting up repos...")
    f = setup_downloader(version=args.network,
                         cacheonly=args.cacheonly,
                         instrepo=args.instrepo,
                         repos=args.repos)

    if args.expire_cache:
        print "expiring cache files"
        f.cleanExpireCache()
        return
    if args.clean_metadata:
        print "cleaning metadata"
        f.cleanMetadata()
        return

    if args.skipkernel:
        message("skipping kernel/initrd download")
    elif f.instrepoid is None or f.instrepoid in f.disabled_repos:
        print _("Error: can't get boot images.")
        if args.instrepo:
            print _("The '%s' repo was rejected by yum as invalid.") % args.instrepo
        else:
            print _("The installation repo isn't available.")
            print "You need to specify one with --instrepo." # XXX temporary
        raise SystemExit(1)
    else:
        print _("getting boot images...")
        kernel, initrd = f.download_boot_images() # TODO: force arch?

    if args.skippkgs:
        message("skipping package download")
    else:
        print _("setting up update...")
        pkgs = download_packages(f)
        # Run a test transaction
        transaction_test(pkgs)

    # And prepare for upgrade
    # TODO: use polkit to get root privs for these things
    print _("setting up system for upgrade")
    if not args.skippkgs:
        prep_upgrade(pkgs)

    if not args.skipbootloader:
        if args.skipkernel:
            print "warning: --skipkernel without --skipbootloader"
            print "using default paths: %s %s" % (kernelpath, initrdpath)
            kernel = kernelpath
            initrd = initrdpath
        prep_boot(kernel, initrd)

    if args.device:
        setup_media_mount(args.device)

    if args.iso:
        fedup.media.umount(args.device.mnt)

    if args.reboot:
        reboot()
    else:
        print _('Finished. Reboot to start upgrade.')

    if f.disabled_repos:
        # NOTE: I hate having a hardcoded list of Important Repos here.
        # This information should be provided by the system, somehow..
        important = ("fedora", "updates")
        if any(i in f.disabled_repos for i in important):
            msg = _("WARNING: Some important repos could not be contacted: %s")
        else:
            msg = _("NOTE: Some repos could not be contacted: %s")
        print msg % ", ".join(f.disabled_repos)
        print _("If you start the upgrade now, packages from these repos will not be installed.")

if __name__ == '__main__':
    args = parse_args()

    # TODO: use polkit to get privs for modifying bootloader stuff instead
    if os.getuid() != 0:
        print _("you must be root to run this program.")
        raise SystemExit(1)

    # set up logging
    if args.debuglog:
        fedup.logutils.debuglog(args.debuglog)
    fedup.logutils.consolelog(level=args.loglevel)
    log.info("%s starting at %s", sys.argv[0], time.asctime())

    try:
        main(args)
    except KeyboardInterrupt:
        print
        log.info("exiting on keyboard interrupt")
        raise SystemExit(1)
    except YumBaseError as e:
        print
        if isinstance(e.value, list):
            err = e.value.pop(0)
            message(_("Downloading failed: %s") % err)
            for p in e.value:
                message("  %s" % p)
        else:
            message(_("Downloading failed: %s") % e)
        log.debug("Exception:", exc_info=True)
        raise SystemExit(2)
    except TransactionError as e:
        print
        message(_("Transaction test failed with the following problems"))
        for p in e.problems:
            message(p)
        log.debug("Exception:", exc_info=True)
        raise SystemExit(3)
    except Exception as e:
        log.info("Exception:", exc_info=True)
        raise
    finally:
        log.info("%s exiting at %s", sys.argv[0], time.asctime())
