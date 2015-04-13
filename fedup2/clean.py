# clean.py - handle the 'clean' command
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

import os, errno, shutil
import logging
log = logging.getLogger("fedup.clean")

def _remove(path, rmfunc=os.unlink):
    try:
        # this is for cleanup - if something else deleted it, that's fine
        if path and os.path.lexists(path):
            rmfunc(path)
    except (IOError, OSError) as e:
        if e.errno != errno.ENOENT:
            log.warn("failed to remove %s: %s", path, str(e))

def remove(path):
    _remove(path, rmfunc=os.unlink)

def remove_dir(path):
    _remove(path, rmfunc=os.rmdir)

def remove_tree(path):
    _remove(path, rmfunc=shutil.rmtree)

class Cleaner(object):
    def __init__(self, cli):
        self.cli = cli
        assert self.cli.state
        assert self.cli.has_lock

    def clean_packages(self):
        '''Remove downloaded packages/images/etc.'''
        remove_tree(self.cli.state.datadir)

    def clean_metadata(self):
        '''Remove cached metadata'''
        remove_tree(self.cli.state.cachedir)

    def clean_bootloader(self):
        '''Remove our boot entry and images'''
        if self.cli.state.kernel:
            boot.remove_entry(self.cli.state.kernel)
        remove(self.cli.state.kernel)
        remove(self.cli.state.initrd)

    def clean_misc(self):
        '''Remove miscellaneous files.'''
        remove_dir("/system-upgrade-root")
        remove("/system-upgrade")
