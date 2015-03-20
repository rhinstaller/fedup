# fedup.cli - CLI for the Fedora Upgrade tool
#
# Copyright (C) 2015 Red Hat Inc.
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

import os, sys, time, argparse, platform

from . import logutils
from .version import version as fedupversion
from .state import get_upgrade_state
from .i18n import _

import logging
log = logging.getLogger("fedup.cli")

def parse_args():
    # === toplevel parser ===
    p = argparse.ArgumentParser(
        usage='%(prog)s <status|download|media|reboot|clean> [OPTIONS]',
        description=_('Prepare system for upgrade.'),
        epilog=_("Use '%(prog)s <ACTION> --help' for more info."),
    )
    # === basic options ===
    p.add_argument('-v', '--verbose', action='store_const', dest='loglevel',
        const=logging.INFO, help=_('print more info'))
    p.add_argument('-d', '--debug', action='store_const', dest='loglevel',
        const=logging.DEBUG, help=_('print lots of debugging info'))
    p.set_defaults(loglevel=logging.WARNING)

    p.add_argument('--log', default='/var/log/fedup.log',
        help=_('where to write log output (default: %(default)s)'))

    p.add_argument('--datadir', default='/var/cache/system-upgrade',
        help=_('where to save data (default: %(default)s)'))

    # === hidden options. FOR DEBUGGING ONLY. ===
    p.add_argument('--logtraceback', action='store_true', default=False,
        help=argparse.SUPPRESS)

    # === subparsers for commands ===
    cmds = p.add_subparsers(dest='action',
        title='Actions', metavar='', prog='fedup',
    )
    s = cmds.add_parser('status',
        help='show upgrade status',
        description='Show the upgrade preparation status.',
    )
    d = cmds.add_parser('download',
        usage='%(prog)s <VERSION> [OPTIONS]',
        help='download data for upgrade',
        description='Download data and boot images for upgrade.',
    )
    r = cmds.add_parser('reboot',
        help='reboot and start upgrade',
        description='Reboot system and start upgrade.',
    )
    c = cmds.add_parser('clean',
        help='clean up data',
        description='Clean up data written by this program.',
    )

    # === options for 'fedup download' ===
    # Translators: This is for '--network [VERSION]' in --help output
    d.add_argument("version", metavar=_('VERSION'), type=VERSION,
        help=_('version to upgrade to (a number or "rawhide")'))
    d.add_argument('--enablerepo', metavar='REPOID', action=RepoAction,
        dest='repos', help=_('enable one or more repos (wildcards allowed)'))
    d.add_argument('--disablerepo', metavar='REPOID', action=RepoAction,
        dest='repos', help=_('disable one or more repos (wildcards allowed)'))
    d.add_argument('--addrepo', metavar='REPOID=URL',
        action=RepoAction, dest='repos',
        help=_('add the repo at URL (use @URL for mirrorlists)'))
    d.add_argument('--instrepo', metavar='URL', type=str,
        help=_('get boot images from this repo (default: automatic)'))
    d.add_argument('--instrepokey', metavar='GPGKEY', type=gpgkeyfile,
        help=_('use this GPG key to verify upgrader boot images'))
    d.set_defaults(repos=[])

    # === DNF plugin options ===
    dnfopts = d.add_argument_group(_('DNF-specific options'))
    dnfopts.add_argument('--enableplugin', metavar='NAME',
        action='append', dest='enable_plugins', default=[],
        help=_('enable DNF plugins (wildcards OK)'))
    dnfopts.add_argument('--disableplugin', metavar='NAME',
        action='append', dest='disable_plugins', default=[],
        help=_('disable DNF plugins (wildcards OK)'))

    pkgopts = d.add_argument_group(_('other options'))
    pkgopts.add_argument('--nogpgcheck', action='store_true', default=False,
        help=_('disable GPG signature checking (not recommended!)'))
    pkgopts.add_argument('--add-install', metavar='<PKG-PATTERN|@GROUP-ID>',
        action='append', dest='add_install', default=[],
        help=_('extra item to be installed during upgrade'))

    # Magical --product option only used for upgrading to Fedora 21
    legacy_fedora = False
    distro, version, id = platform.linux_distribution(supported_dists='fedora')
    if distro.lower() == 'fedora' and int(version) < 21:
        legacy_fedora = True
        pkgopts.add_argument('--product', default=None,
            choices=('server','cloud','workstation','nonproduct'),
            help=_('Fedora product to install (for upgrades to F21)'))

    # === options for 'fedup clean' ===
    c.add_argument('clean', metavar='CLEAN_ARG',
        help=_('what to clean up')+' (%(choices)s)',
        choices=('packages','bootloader','metadata','misc','all'),
    )

    # === PARSER READY!! BEGIN THE PARSING!! ===

    # Backward-compatibility: 'fedup --clean' --> 'fedup clean all'
    argv = sys.argv[1:]
    if argv and argv[0] == '--clean':
        argv[0] = 'clean'
        if len(argv) == 1:
            argv.append("all")
        print(_("WARNING: --clean is deprecated; doing '%s'") % ' '.join(argv))

    # PARSE IT UP
    args = p.parse_args(argv)

    # An action is required
    if not args.action:
        p.error(_('no action given.'))

    # Save this so we can use it elsewhere
    args.legacy_fedora = legacy_fedora

    # Everything after this just checks 'download' args; exit early otherwise
    if args.action != 'download':
        return args

    # handle --instrepo URL (default is to interpret it as a repoid)
    if args.instrepo and '://' in args.instrepo:
        args.repos.append(('add', 'instrepo=%s' % args.instrepo))
        args.instrepo = 'instrepo'

    if args.instrepo and args.instrepokey:
        args.repos.append(('gpgkey', 'instrepo=%s' % args.instrepokey))

    # Fedora.next: upgrades to F21 require --product
    # FIXME split this more sensibly from above junk
    if args.legacy_fedora:
        if args.product is None:
            # fail early if we can detect that you need a product
            if int(version) == 20 or args.network in ('21', '22', 'rawhide'):
                p.error(fedora_next_error)
        elif args.product == 'nonproduct':
            args.add_install.append('fedora-release-nonproduct')
        else:
            args.add_install.append('@^%s-product-environment' % args.product)

    return args

class RepoAction(argparse.Action):
    '''Hold a list of repo actions so we can apply them in the order given.'''
    def __call__(self, parser, namespace, value, opt=None):
        curval = getattr(namespace, self.dest, [])
        action = ''
        if opt.startswith('--enable'):
            action = 'enable'
        elif opt.startswith('--disable'):
            action = 'disable'
        elif opt.startswith('--addrepo'):
            action = 'add'
            # validate the argument
            repoid, eq, url = value.partition("=")
            if not (repoid and eq and "://" in url):
                raise argparse.ArgumentError(self,
                                        _("value should be REPOID=[@]URL"))
        curval.append((action, value))
        setattr(namespace, self.dest, curval)

# validate a GPGKEY argument and return a URI ('file:///...')
def gpgkeyfile(arg):
    if arg.startswith('file://'):
        arg = arg[7:]
    gpghead = '-----BEGIN PGP PUBLIC KEY BLOCK-----'
    try:
        with open(arg) as keyfile:
            keyhead = keyfile.read(len(gpghead))
    except (IOError, OSError) as e:
        raise argparse.ArgumentTypeError(e.strerror)
    if keyhead != gpghead:
        raise argparse.ArgumentTypeError(_("File is not a GPG key"))
    return 'file://' + os.path.abspath(arg)

def VERSION(arg):
    if arg.lower() == 'rawhide':
        return 'rawhide'

    _distros=('fedora', 'redhat', 'centos')
    distro, version, id = platform.linux_distribution(supported_dists=_distros)

    try:
        floatver = float(version)
    except ValueError:
        raise argparse.ArgumentTypeError(_("can't determine system version"))
    if float(arg) <= floatver:
        raise argparse.ArgumentTypeError(_("version must be higher than %s")
                                         % version)
    return arg

# special Fedora-21-specific error message
fedora_next_error = '\n' + _('''
This installation of Fedora does not belong to a product, so you
must provide the --product=PRODUCTNAME option to specify what product
you want to upgrade to. PRODUCTNAME should be one of:

 workstation: the default Fedora experience for laptops and desktops,
   powered by GNOME.
 server: the default Fedora experience for servers
 cloud: a base image for use on public and private clouds
 nonproduct: choose this if none of the above apply; in particular,
   choose this if you are using an alternate-desktop spin of Fedora

Selecting a product will also install its standard package-set in
addition to upgrading the packages already on your system. If you
prefer to maintain your current set of packages, select 'nonproduct'.

See https://fedoraproject.org/wiki/Upgrading for more information.
''')

def sanity_check(args):
    if os.getuid() != 0:
        print(_("you must be root to do this."))
        raise SystemExit(1)

def open_logs(args):
    try:
        logutils.debuglog(args.log)
    except IOError as e:
        print(_("Can't open logfile '%s': %s") % (args.log, e))
        raise SystemExit(1)
    logutils.consolelog(level=args.loglevel)

def status():
    distro, version, id = platform.linux_distribution(supported_dists='fedora')
    print("Current system: %s %s" % (distro.capitalize(), version))
    state = get_upgrade_state()
    print(state.summary)

def download(args):
    print('DOWNLOAD!!!! FIXME!! YESSS')
    print(args)

def main():
    args = parse_args()

    if args.action == 'status':
        status()
        return

    sanity_check(args)
    open_logs(args)
    exittype = "cleanly"

    try:
        log.info("fedup %s starting at %s", fedupversion, time.asctime())
        log.info("argv: %s", str(sys.argv))
        if args.action == 'download':
            download(args)
        elif args.action == 'clean':
            clean(args)
        elif args.action == 'reboot':
            reboot(args)
    except KeyboardInterrupt as e:
        log.info("exiting on keyboard interrupt")
        if args.logtraceback:
            log.debug("Traceback (for debugging purposes):", exc_info=True)
    finally:
        log.info("fedup %s exiting %s at %s", fedupversion, exittype, time.asctime())
