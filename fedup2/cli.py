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

import os, sys, time, argparse

from . import logutils
from .version import version as fedupversion
from .state import State
from .lock import PidLock, PidLockError
from .sysinfo import get_distro
from .clean import Cleaner
from .reboot import Bootprep, reboot

from .i18n import _

import logging
log = logging.getLogger("fedup")

def is_legacy_fedora():
    distro, version = get_distro()
    return bool(distro.lower() == 'fedora' and int(version) < 21)

def init_parser():
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
    p.add_argument('--legacy-fedora',action='store_true', default=False,
        help=argparse.SUPPRESS)
    p.add_argument('--sleep-forever',action='store_const', const='sleep',
        dest='action', help=argparse.SUPPRESS)
    p.add_argument('--cachedir', help=argparse.SUPPRESS)

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
    d.add_argument('--instrepoid', metavar='REPOID', action=RepoAction,
        dest='repos', help=_('get boot images from repo with id REPOID'))
    d.add_argument('--instrepo', metavar='URL', action=RepoAction,
        dest='repos', help=_('get boot images from the repo at this URL'))
    d.add_argument('--instrepokey', metavar='GPGKEY', type=gpgkeyfile,
        help=_('use this GPG key to verify boot images'))
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
    if is_legacy_fedora():
        p.set_defaults(legacy_fedora=True)
        pkgopts.add_argument('--product',
            action='append', dest='add_install', type=PRODUCT,
            choices=('server','cloud','workstation','nonproduct'),
            help=_('Fedora product to install (for upgrades to F21)'))

    # === options for 'fedup clean' ===
    c.add_argument('clean', metavar='CLEAN_ARG',
        help=_('what to clean up')+' (%(choices)s)',
        choices=('packages','bootloader','metadata','misc','all'),
    )
    return p

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
        elif opt.startswith('--instrepokey'):
            action = 'gpgkey'
            value = 'instrepo='+value # XXX is that the right repo name?
        elif opt.startswith('--instrepo'):
            action = 'add'
            value = "cli_instrepo="+value
        if action == 'add':
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

    distro, version = get_distro()
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

class Cli(object):
    """The main fedup CLI object."""
    def __init__(self):
        self.parser = init_parser()
        self.args = None
        self.state = None
        self.exittype = "cleanly"
        self.has_lock = False
        self.continued = False
        self.reboot_at_exit = False

    def error(self, msg, *args):
        log.error(msg, *args)
        raise SystemExit(2)

    def message(self, msg, *args):
        log.info(msg, *args)
        if self.args and self.args.loglevel > logging.INFO:
            print(msg % args)

    def parse_args(self):
        assert self.parser
        self.args = self.parser.parse_args()

    def read_state(self):
        self.state = State()

    def check_args(self):
        """Check (and fix up) the args we got from parse_args."""
        assert self.args

        # An action is required
        if not self.args.action:
            self.parser.error(_('no action given.'))

        # If we need --product, make sure it was supplied
        if self.args.legacy_fedora:
            if self.args.product:
                self.fix_product()
            elif self.need_product():
                self.error(fedora_next_error)

    def check_state(self):
        """Check the saved state to see if it's compatible with this action"""
        assert self.args
        assert self.state

        # Can't reboot if we're not actually ready to upgrade
        if self.args.action == 'reboot' and not self.state.upgrade_ready:
            if self.state.args:
                self.error(_("download incomplete"))
            else:
                self.error(_("system not prepared for upgrade"))

        # If we have a previously-interrupted download
        if self.args.action == 'download' and self.state.args:
            if self.args._continue:
                self.args = self.state.args
                self.continued = True
            elif self.args.abort:
                pass # we'll handle this after we get the lock.
            else:
                log.error(_("interrupted download detected!"))
                log.error(_("use `fedup download --continue` to continue it."))
                log.error(_("use `fedup download --abort` to start over."))
                raise SystemExit(2)

    def need_product(self):
        if self.args.version == 'rawhide' or int(self.args.version) >= 21:
            if self.args.legacy_fedora and not has_product_installed():
                return True

    def fix_product(self):
        if product == 'nonproduct':
            self.args.add_install.append('fedora-release-nonproduct')
        else:
            self.args.add_install.append('@^%s-product-environment' % product)

    def check_perms(self):
        if os.getuid() != 0:
            self.error(_("you must be root to do this."))

    def open_logs(self):
        try:
            logutils.log_setup(self.args.log, self.args.loglevel)
        except IOError as e:
            self.error(_("Can't open logfile '%s': %s"), self.args.log, e)
        log.info("fedup %s starting at %s", fedupversion, time.asctime())
        log.info("argv: %s", str(sys.argv))

    def get_lock(self):
        try:
            self.pidfile = PidLock("/var/run/fedup.pid")
            self.has_lock = True
        except PidLockError as e:
            self.error(_("already running as PID %s") % e.pid)

    def free_lock(self):
        assert self.pidfile
        self.pidfile.remove()
        self.has_lock = False

    def write_packagelist(self, packagepaths):
        with open(os.path.join(self.args.datadir, "packages.list"),'w') as outf:
            for p in packagepaths:
                outf.write(os.path.relpath(p, self.args.datadir)+'\n')

    def status(self):
        print("Current system: %s %s" % (get_distro()))
        print(self.state.summarize())

    def download(self):
        # special case for `fedup download --abort`
        if self.args.abort:
            with self.state:
                self.state.clear()
            return
        # write initial state, if needed
        if not self.continued:
            with self.state as state:
                state.upgrade_target = args.version
                state.pkgdir = args.datadir
                state.args = args
        # set up downloader
        dl = Downloader(args)
        dl.setup()
        dl.read_metadata()
        # download boot images
        kernel, initrd = dl.download_images()
        with self.state as state:
            state.kernel = kernel
            state.initrd = initrd
        # find updates
        pkglist = dl.find_upgrade_packages()
        with self.state as state:
            state.pkgs_total = len(pkglist)
            state.size_total = sum(p.size for p in pkglist)
        # TODO: sanity-check pkglist
        # download packages
        dl.download_packages(pkglist)
        # TODO: run a test transaction
        self.write_packagelist(p.localPkg() for p in pkglist)
        # we're done! mark it, dude!
        with self.state as state:
            state.upgrade_ready = 1

    def reboot(self):
        r = Bootprep(self)
        r.copy_boot_images()
        r.prep_boot()
        # signal for reboot
        self.reboot_at_exit = True

    def clean(self):
        cleaner = Cleaner(self)
        if self.args.clean == 'all':
            cleaner.clean_bootloader()
            cleaner.clean_packages()
            cleaner.clean_metadata()
            cleaner.clean_misc()
        elif self.args.clean == 'bootloader':
            cleaner.clean_bootloader()
        elif self.args.clean == 'packages':
            cleaner.clean_packages()
        elif self.args.clean == 'metadata':
            cleaner.clean_metadata()
        elif self.args.clean == 'misc':
            cleaner.clean_misc()
        else:
            raise AssertionError("invalid 'clean' arg")


    def sleep(self):
        print("pid %u, now going to sleep forever!" % os.getpid())
        while True:
            time.sleep(31337)

    def main(self):
        self.parse_args()
        self.check_args()
        self.read_state()
        self.check_state()

        if self.args.action == 'status':
            self.status()
            return

        self.check_perms()
        self.open_logs()
        self.get_lock()

        try:
            if self.args.action == 'download':
                self.download()
            elif self.args.action == 'clean':
                self.clean()
            elif self.args.action == 'reboot':
                self.reboot()
            elif self.args.action == 'sleep':
                self.sleep()
        except KeyboardInterrupt as e:
            log.info(_("exiting on keyboard interrupt"))
            raise SystemExit(1)
        except Exception as e:
            log.info("Exception:", exc_info=True)
            exittype = "with unhandled exception"
            raise
        finally:
            log.info("fedup %s exiting %s at %s",
                     fedupversion, self.exittype, time.asctime())
            self.free_lock()
            if self.reboot_at_exit:
                reboot()
