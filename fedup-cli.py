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

from fedup.download import FedupDownloader, YumBaseError, link_pkgs
from fedup.upgrade import FedupUpgrade, TransactionError
from fedup import textoutput as output

import logging, fedup.logutils
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

def prep_upgrade(pkgs):
    print _("setting up system for upgrade")
    # put packages in packagedir (also writes packagelist)
    link_pkgs(pkgs)

    # FIXME: modify bootloader config (grub2-reboot)

def reboot():
    call(['systemctl', 'reboot'])

def get_versions():
    '''Possible versions to upgrade to. Given Fedora N, this is N+1 and N+2.'''
    distro, version, id = platform.linux_distribution()
    version = int(version)
    return [str(version+1), str(version+2)]

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
                               _('Specify the location of the upgrade data.'))
    req.add_argument('--iso',
        help='[TODO] '+_('Installation image file'))
    # Translators: This is for '--device DEVICE' in --help output
    req.add_argument('--device', metavar=_('DEVICE'),
        help='[TODO] '+_('Installation image on device (DVD, USB, etc.)'))
    # Translators: This is for '--network [VERSION]' in --help output
    req.add_argument('--network', metavar=_('VERSION'), nargs='?',
        const='latest', choices=['latest', 'rawhide'] + get_versions(),
        help=_('Download VERSION from the network (default: newest release)'))

    net = p.add_argument_group(_('optional arguments for --network'))
    net.add_argument('--disablerepo', metavar='REPO', action=RepoAction,
        dest='repos', help=_('Repositories to disable for network upgrade'))
    net.add_argument('--enablerepo', metavar='REPO', action=RepoAction,
        dest='repos', help=_('Repositories to enable for network upgrade'))
    # TODO: arbitrary repos with --repourl
    p.set_defaults(repos=[])

    args = p.parse_args()

    if not (args.network or args.device or args.iso):
        p.error(_('One of (--network, --device, --iso) is required.'))

    return args

def main(args):
    # Get our packages set up where we can use 'em
    # TODO: FedupMedia setup for DVD/USB/ISO
    if args.network:
        if args.network == 'latest':
            # FIXME: fetch releases.txt to determine this
            args.network = '18'
        pkgs = download_pkgs(version=args.network, repos=args.repos)
    else:
        print "Upgrade from local media not implemented yet!"
        raise SystemExit(255)

    # FIXME: fetch kernel & initrd

    # Run a test transaction
    transaction_test(pkgs)

    # And prepare for upgrade
    # TODO: need root privs here
    prep_upgrade(pkgs)

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
