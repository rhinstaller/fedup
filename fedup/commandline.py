# fedup.commandline - commandline parsing functions
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

import os, argparse, platform

import fedup.media
from fedup.download import reset_boot, remove_boot, remove_cache, misc_cleanup
from fedup import _

import logging
log = logging.getLogger("fedup")

def parse_args(gui=False):
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
    p.add_argument('--skipbootloader', action='store_true', default=False,
        help=argparse.SUPPRESS)
    p.add_argument('-C', '--cacheonly', action='store_true', default=False,
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

    if not gui:
        clean = p.add_argument_group(_('cleanup commands'))

        clean.add_argument('--resetbootloader', action='store_const',
            dest='clean', const='bootloader', default=None,
            help=_('remove any modifications made to bootloader'))
        clean.add_argument('--clean', action='store_const', const='all',
            help=_('clean up everything written by fedup'))
        p.add_argument('--expire-cache', action='store_true', default=False,
            help=argparse.SUPPRESS)
        p.add_argument('--clean-metadata', action='store_true', default=False,
            help=argparse.SUPPRESS)

    args = p.parse_args()

    if not (args.network or args.device or args.iso or args.clean):
        p.error(_('SOURCE is required (--network, --device, --iso)'))

    # allow --instrepo URL as shorthand for --repourl REPO=URL --instrepo REPO
    if args.instrepo and '://' in args.instrepo:
        args.repos.append(('add', 'cmdline-instrepo=%s' % args.instrepo))
        args.instrepo = 'cmdline-instrepo'

    if not gui:
        if args.clean:
            args.resetbootloader = True

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

def device_setup(args):
    # treat --device like --repo REPO=file://$MOUNTPOINT
    if args.device:
        args.repos.append(('add', 'fedupdevice=file://%s' % args.device.mnt))
        args.instrepo = 'fedupdevice'
    elif args.iso:
        try:
            args.device = fedup.media.loopmount(args.iso)
        except fedup.media.CalledProcessError as e:
            log.info("mount failure: %s", e.output)
            message('--iso: '+_('Unable to open %s') % args.iso)
            raise SystemExit(2)
        else:
            args.repos.append(('add', 'fedupiso=file://%s' % args.device.mnt))
            args.instrepo = 'fedupiso'
