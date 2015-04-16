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

from dnf.util import ensure_dir
from subprocess import check_output, PIPE

from .i18n import _
import logging
log = logging.getLogger("fedup.reboot")

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

class Bootprep(object):
    def __init__(self, cli):
        self.cli = cli

    def copy_boot_images(self):
        kernelpath = get_kernel_path(kernelname)
        initrdpath = get_initrd_path(kernelname)
        copy2(self.cli.state.kernel, kernelpath)
        # FIXME: modify initrd here
        copy2(self.cli.state.initrd, initrdpath)
        with self.cli.state as state:
            state.boot_name = kernelname
            state.boot_kernel = kernelpath
            state.boot_initrd = initrdpath

    def prep_boot(self):
        # TODO: make magic symlink to self.cli.state.datadir
        # make upgraderoot dir
        ensure_dir('/system-upgrade-root')
        # make empty module dir for new kernel
        kv = kernel_version(self.cli.state.boot_kernel)
        ensure_dir(os.path.join('/lib/modules', kv))
        # add our boot entry
        add_boot_entry(self.cli.state.kernelname)
