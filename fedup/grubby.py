# fedup.grubby - bootloader config modification code for the Fedora Upgrader
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

from subprocess import check_output, CalledProcessError, PIPE
from collections import namedtuple

GrubbyEntry = namedtuple("GrubbyEntry", "index kernel args root initrd title")

class Grubby(object):
    '''View/manipulate bootloader configuration using `grubby`.'''

    bootloaders = ("grub", "grub2", "elilo", "extlinux",
                   "lilo", "silo", "yaboot", "zipl")

    def __init__(self, config=None, bootloader=None):
        self.config = config
        self.bootloader = bootloader

        if bootloader and bootloader not in self.bootloaders:
            raise ValueError("bootloader must be one of: %s" % \
                                " ".join(self.bootloaders))

    def _grubby(self, *args):
        cmd = ["grubby"]
        if self.bootloader:
            cmd += ["--%s" % bootloader]
        if self.config:
            cmd += ["--config-file", config]
        return check_output(cmd + [str(a) for a in args], stderr=PIPE)

    def get_entry(self, index):
        '''Returns a GrubbyEntry for the entry at the given index,
        or None if index < 0.'''
        index = int(index) # make sure index is int
        # NOTE: current grubby (8.12-1) doesn't accept --info {-2,-3}, so..
        if index < 0:
            return None
        out = self._grubby("--info", index)
        info = dict()
        for line in out.split("\n"):
            k, eq, val = line.partition('=')
            if k and val:
                if k == 'index':
                    info[k]=int(val)
                else:
                    info[k]=val
        return GrubbyEntry(**info)

    def get_entries(self):
        ents = []
        for n in xrange(64): # an arbitrary but reasonable limit
            try:
                ents.append(self.get_entry(n))
            except CalledProcessError:
                break
        return ents

    def default_index(self):
        '''Return the index of the default boot item.
        NOTE: May return -1 (no default), -2 or -3 (saved default, grub1/2)'''
        return int(self._grubby("--default-index"))

    def default_entry(self):
        return self.get_entry(self.default_index())

    def set_default_entry(self, index):
        index = int(index) # make sure index is int
        self._grubby("--set-default", index)

    def add_entry(self, kernel, initrd, title,
                        args=None, copydefault=True, makedefault=False):
        '''
        Add a boot entry with the given parameters.
        If copydefault is True, 'args' will be appended to the args from
        the current default entry.
        If makedefault is True, the new entry will be made the default.
        '''
        grubby_args = ["--add-kernel", kernel, "--title", title]
        if initrd:
            grubby_args += ["--initrd", initrd]
        if args:
            grubby_args += ["--args", args]
        if copydefault:
            grubby_args += ["--copy-default"]
        if makedefault:
            grubby_args += ["--make-default"]
        self._grubby(*grubby_args)

    def update_entry(self, index, add_args=None, remove_args=None):
        '''
        Note that update_entry currently cannot modify anything except the
        boot args; if you need to change the title etc. you will probably
        need to create a new entry and delete the old one.
        '''
        index = int(index) # make sure index is int
        grubby_args = ["--update-kernel", str(index)]
        if add_args:
            grubby_args += ["--args", add_args]
        if remove_args:
            grubby_args += ["--remove-args", remove_args]
        self._grubby(*grubby_args)

    def remove_entry(self, index):
        index = int(index) # make sure index is int
        self._grubby("--remove-kernel", index)

