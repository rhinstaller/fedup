# reboot.py - handle the 'reboot' command
#
# Copyright (c) 2015 Red Hat, Inc.
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

import os, struct

from dnf.util import ensure_dir
from subprocess import check_output, PIPE
from shutil import copy2

from .i18n import _
import logging
log = logging.getLogger("fedup.reboot")

__all__ = (
    'Bootprep',
    'add_boot_entry',
    'remove_boot_entry',
    'reboot',
)

kernelname = 'fedup'

def get_kernel_path(kver=kernelname):
    return '/boot/vmlinuz-%s' % kver
def get_initrd_path(kver=kernelname):
    return '/boot/initramfs-%s.img' % kver

def add_boot_entry(kver):
    log.info("adding %r boot entry", kver)
    cmd = ["/sbin/new-kernel-pkg", "--initrdfile", get_initrd_path(kver),
                                   "--banner", _("System Upgrade"),
                                   "--make-default",
                                   "--install", get_kernel_path(kver)]
    return check_output(cmd, stderr=PIPE)

def remove_boot_entry(kver):
    if not kver:
        return
    log.info("removing %r boot entry", kver)
    cmd = ["/sbin/new-kernel-pkg", "--remove", get_kernel_path(kver)]
    return check_output(cmd, stderr=PIPE)

def reboot():
    log.info("initiating reboot")
    cmd = ["systemctl","reboot"]
    return check_output(cmd, stderr=PIPE)

def kernel_version(filename):
    '''read the version number out of a vmlinuz file.'''
    # this algorithm adapted from /usr/share/magic
    with open(filename) as f:
        f.seek(514)
        if f.read(4) != 'HdrS':
            return None
        f.seek(526)
        (offset,) = struct.unpack("<H", f.read(2))
        f.seek(offset+0x200)
        buf = f.read(256)
    uname = buf[:buf.find('\0')]
    version = uname[:uname.find(' ')]
    return version

def find_mount(path):
    return os.stat(path).st_dev # XXX: don't think this is reliable on btrfs

class Bootprep(object):
    def __init__(self, cli):
        self.cli = cli

    def copy_boot_images(self):
        kernelpath = get_kernel_path(kernelname)
        initrdpath = get_initrd_path(kernelname)
        copy2(self.cli.state.kernel, kernelpath)
        # TODO: modify initrd here, if we're still using fedup-dracut
        copy2(self.cli.state.initrd, initrdpath)
        with self.cli.state as state:
            state.boot_name = kernelname
            state.boot_kernel = kernelpath
            state.boot_initrd = initrdpath

    def prep_mount_units(self):
        # What mounts do we need to make the upgrade work?
        pkgdirs = set(os.path.dirname(p) for p in self.cli.state.packagelist)
        need_mounts = set(find_mount(d) for d in pkgdirs)
        # What mounts are we *definitely* going to have after we reboot?
        # XXX: this is a weak-ass heuristic. Can we ask systemd?
        sysdirs = set(("/","/usr","/boot"))
        have_mounts = set(find_mount(d) for d in sysdirs)
        for m in need_mounts.difference(have_mounts):
            self.cli.error("OH POOP YOU NEED MORE MOUNTS: %s", m)
            # TODO: generate a mount unit for m and save it to wantdir
            #wantdir = '/lib/systemd/system/system-upgrade.target.wants'

    def prep_boot(self):
        # make the magic symlink
        os.symlink(self.cli.state.datadir, "/system-upgrade")
        # make upgraderoot dir
        ensure_dir('/system-upgrade-root')
        # make empty module dir for new kernel
        kv = kernel_version(self.cli.state.boot_kernel)
        ensure_dir(os.path.join('/lib/modules', kv))
        # prepare mount units for everything listed in packagelist
        self.prep_mount_units()
        # add our boot entry
        add_boot_entry(self.cli.state.kernelname)
