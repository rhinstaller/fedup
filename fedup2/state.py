# state.py - track upgrade state in a well-known place
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

import os
try:
    from configparser import *
except ImportError:
    from ConfigParser import *

import shlex
try:
    from shlex import quote as _quote
except ImportError:
    from pipes import quote as _quote

from .i18n import _
from argparse import Namespace

import logging
log = logging.getLogger("fedup.state")

__all__ = ['State']

def shelljoin(argv):
    return ' '.join(_quote(a) for a in argv)

def shellsplit(cmdstr):
    return shlex.split(cmdstr or '')

class State(object):
    statefile = '/var/lib/system-upgrade/upgrade.conf'
    def __init__(self):
        self._conf = RawConfigParser()
        self._conf.read(self.statefile)
        self.args = None

    def _get(self, section, option):
        try:
            return self._conf.get(section, option)
        except (NoSectionError, NoOptionError):
            return None

    def _set(self, section, option, value):
        try:
            self._conf.add_section(section)
        except DuplicateSectionError:
            pass
        self._conf.set(section, option, value)
        log.debug("set %s.%s=%s", section, option, value)

    def _del(self, section, option):
        try:
            self._conf.remove_option(section, option)
            log.debug("del %s.%s", section, option)
        except NoSectionError:
            pass

    def write(self):
        with open(self.statefile, 'w') as outf:
            self._conf.write(outf)

    def clear(self):
        self._conf = RawConfigParser()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.write()

    def _configprop(section, option, encode=None, decode=None, doc=None):
        def getprop(self):
            value = self._get(section, option)
            if callable(decode) and value is not None:
                value = decode(value)
            return value
        def setprop(self, value):
            if callable(encode):
                value = encode(value)
            self._set(section, option, value)
        def delprop(self):
            self._del(section, option)
        return property(getprop, setprop, delprop, doc)

    # cached/local boot images
    kernel = _configprop("upgrade", "kernel")
    initrd = _configprop("upgrade", "initrd")

    # boot images, in situ
    boot_name = _configprop("boot", "name")
    boot_kernel = _configprop("boot", "kernel")
    boot_initrd = _configprop("boot", "initrd")

    current_system = _configprop("system", "distro")

    upgrade_target = _configprop("upgrade", "target")
    upgrade_ready = _configprop("upgrade", "ready")

    pkgs_total = _configprop("download", "pkgs_total")
    size_total = _configprop("download", "size_total")
    datadir = _configprop("download", "datadir")
    cmdline = _configprop("download", "cmdline",
                          encode=shelljoin,
                          decode=shellsplit)

    def summarize(self):
        if not self.upgrade_target:
            return _("No upgrade in progress.")
        elif not self.upgrade_ready:
            return _("Upgrade to %s in progress.") % self.upgrade_target
        else:
            return _("Ready to start upgrade to %s") % self.upgrade_target
