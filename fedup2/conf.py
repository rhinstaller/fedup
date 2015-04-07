# conf.py - config parser
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

import os
from tempfile import mkstemp
try:
    from ConfigParser import *
except ImportError:
    from configparser import *

class Config(RawConfigParser):
    def __init__(self, filename, defaults=None):
        RawConfigParser.__init__(self, defaults)
        self.filename = filename
        self.read(filename)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.write()

    def writefp(self, fp):
        RawConfigParser.write(self, fp)

    def write(self):
        with open(self.filename, 'w') as outf:
            self.writefp(outf)

    def add_section(self, section, duplicate_ok=True):
        '''Add the named section, raising DuplicateSectionError if the section
        exists and duplicate_ok is False.'''
        try:
            RawConfigParser.add_section(self, section)
        except DuplicateSectionError:
            if not duplicate_ok:
                raise

    def set(self, section, option, value=None):
        '''Set an option, creating the section if needed.'''
        self.add_section(section)
        RawConfigParser.set(self, section, option, value)

    def get(self, section, option):
        '''Get an option, returning None if missing'''
        value = None
        try:
            value = RawConfigParser.get(self, section, option)
        except (NoSectionError, NoOptionError):
            pass
        return value

    def remove(self, section, option):
        '''Remove an option, removing the section if it is now empty'''
        self.remove_option(section, option)
        if not self.items(section):
            self.remove_section(section)
