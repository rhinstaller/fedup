#!/usr/bin/python
#
# BLAH GPL BLAH
#
# Copyright 2012 Red Hat Inc.
#
# Author: Will Woods <wwoods@redhat.com>

import os, sys, time
import argparse, platform
from subprocess import call

from fedup.download import FedupDownloader, YumBaseError, prep_upgrade
from fedup.upgrade import FedupUpgrade, TransactionError
from fedup import textoutput as output

import logging, fedup.logutils, fedup.media
log = logging.getLogger("fedup")
fedup.logutils.debuglog("fedup.log") # FIXME: better dir for this
fedup.logutils.consolelog()          # TODO: control output with cli args

from fedup import _

def download_pkgs(version, repos=[]):
    log.debug("download_pkgs(version=%s, repos=%s)", version, repos)
    print _("setting up repos...")
    f = FedupDownloader(version=version)
    repo_cb = output.RepoCallback()
    repo_prog = output.RepoProgress(fo=sys.stderr)
    disabled_repos = f.setup_repos(callback=repo_cb,
                                   progressbar=repo_prog,
                                   repos=repos)
    if disabled_repos:
        print _("No upgrade available for the following repos") + ": " + \
                " ".join(disabled_repos)

    print _("setting up update...")
    updates = f.build_update_transaction(callback=output.DepsolveCallback(f))
    # clean out any unneeded packages from the cache
    f.clean_cache(keepfiles=(p.localPkg() for p in updates))
    # download packages
    f.download_packages(updates, callback=output.DownloadCallback())

    return set(po.localPkg() for po in updates)

def transaction_test(pkgs):
    print _("testing upgrade transaction")
    fu = FedupUpgrade()
    fu.setup_transaction(pkgfiles=pkgs)
    fu.test_transaction(callback=output.TransactionCallback(numpkgs=len(pkgs)))

def reboot():
    call(['systemctl', 'reboot'])

## argument parsing stuff ##
# TODO: move to fedup/parse_args.py so it can be shared with GUI?

class RepoAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        curval = getattr(namespace, self.dest, [])
        action = ''
        if option_string.startswith('--enable'):
            action = 'enable'
        elif option_string.startswith('--disable'):
            action = 'disable'
        curval.append((action, value))
        setattr(namespace, self.dest, curval)

# check the argument to '--device' to see if it refers to install media
def device_or_mnt(arg):
    if arg == 'auto':
        media = fedup.media.find()
    else:
        media = [m for m in fedup.media.find() if arg in (m.dev, m.mntpoint)]

    if len(media) == 1:
        return media.pop()

    if not media:
        msg = _("no install media found")
        if arg != 'auto':
            msg = "%s: %s" % (arg, msg)
    else:
        devs = ", ".join(m.dev for m in media)
        msg = _("multiple devices found. please choose one of (%s)") % devs
    raise argparse.ArgumentTypeError(msg)

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

    p.add_argument('--reboot', action='store_true', default=False,
        help=_('Automatically reboot to start the upgrade when ready'))
    p.add_argument('--sshd', action='store_true', default=False,
        #help=_('Enable sshd during the upgrade (for remote monitoring)'))
        help='[TODO] '+_('Enable sshd during the upgrade (for remote monitoring)'))

    req = p.add_argument_group('SOURCE',
                               _('Location to search for upgrade data.'))
    req.add_argument('--device', metavar='DEV', nargs='?',
        type=device_or_mnt, const='auto',
        help=_('device or mountpoint. default: check mounted devices'))
    req.add_argument('--iso',
        help='[TODO] '+_('installation image file'))
    # Translators: This is for '--network [VERSION]' in --help output
    req.add_argument('--network', metavar=_('VERSION'), type=VERSION,
        help=_('online repos matching VERSION (a number or "rawhide")'))

    net = p.add_argument_group(_('optional arguments for --network'))
    net.add_argument('--enablerepo', metavar='REPO', action=RepoAction,
        dest='repos', help=_('enable one or more repos (wildcards allowed)'))
    net.add_argument('--disablerepo', metavar='REPO', action=RepoAction,
        dest='repos', help=_('disable one or more repos (wildcards allowed)'))
    p.set_defaults(repos=[])

    args = p.parse_args()

    if not (args.network or args.device or args.iso):
        p.error(_('SOURCE is required (--network, --device, --iso)'))

    return args

def main(args):
    # Get our packages set up where we can use 'em
    # TODO: FedupMedia setup for DVD/USB/ISO
    if args.network:
        if args.network == 'latest':
            # FIXME: fetch releases.txt to determine this
            args.network = '18'
        pkgs = download_pkgs(version=args.network, repos=args.repos)
        # FIXME: fetch kernel & initrd
    else:
        if args.iso:
            # FIXME: mount iso so we can use files etc.
            # FIXME: set args.device = FstabEntry for mounted iso
            raise NotImplementedError("--iso isn't implemented yet")
        # FIXME: set up repo for args.device.mntpoint
        # FIXME: prep update transaction, get pkglist for repo
        # FIXME: copy kernel & initrd into place
        raise NotImplementedError("--device isn't implemented yet")

    # Run a test transaction
    transaction_test(pkgs)

    # And prepare for upgrade
    # TODO: we need root privs here... use polkit to get 'em?
    print _("setting up system for upgrade")
    prep_upgrade(pkgs)
    # FIXME: args.bootloader
    # FIXME: if args.device: add ${dev}.mount to system-update.target.wants

    if args.reboot:
        reboot()
    else:
        print _('Finished. Reboot to start upgrade.')

if __name__ == '__main__':
    args = parse_args()
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
            print _("Downloading failed: %s") % err
            for p in e.value:
                print "  %s" % p
        else:
            print _("Downloading failed: %s") % e
        raise SystemExit(2)
    except TransactionError as e:
        print
        print _("Transaction test failed with the following problems")
        for p in e.problems:
            print p
        raise SystemExit(3)
    finally:
        # TODO: log exception
        log.info("%s exiting at %s", sys.argv[0], time.asctime())
