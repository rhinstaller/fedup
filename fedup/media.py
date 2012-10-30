# fedup.media - check for installable media
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

import os, stat
from collections import namedtuple
from os.path import exists, join

FstabEntry = namedtuple('FstabEntry', 'dev mntpoint type opts freq passno')

def mounts(fstab="/proc/mounts"):
    for line in open(fstab):
        yield FstabEntry(*line.split())

def ismedia(mountpoint):
    return exists(join(mountpoint, ".buildstamp"))

def isblock(dev):
    return exists(dev) and stat.S_ISBLK(os.stat(dev).st_mode)

def find():
    return [m for m in mounts() if isblock(m.dev) and ismedia(m.mntpoint)]
