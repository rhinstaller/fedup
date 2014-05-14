# util.py - various shared utility functions
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

import os, struct
from shutil import rmtree
from tempfile import mkdtemp

import logging
log = logging.getLogger(__package__+".util")

try:
    from ctypes import cdll, c_bool
    selinux = cdll.LoadLibrary("libselinux.so.1")
    is_selinux_enabled = selinux.is_selinux_enabled
    is_selinux_enabled.restype = c_bool
except (ImportError, AttributeError, OSError):
    is_selinux_enabled = lambda: False

def listdir(d):
    for f in os.listdir(d):
        yield os.path.join(d, f)

def rlistdir(d):
    for root, files, dirs in os.walk(d):
        for f in files:
            yield os.path.join(root, f)

def mkdir_p(d):
    try:
        os.makedirs(d)
    except OSError as e:
        if e.errno != 17:
            raise

def rm_f(f, rm=os.remove):
    if not os.path.lexists(f):
        return
    try:
        rm(f)
    except (IOError, OSError) as e:
        log.warn("failed to remove %s: %s", f, str(e))

def rm_rf(d):
    if os.path.isdir(d):
        rm_f(d, rm=rmtree)
    else:
        rm_f(d)

def kernelver(filename):
    '''read the version number out of a vmlinuz file.'''
    # this algorithm came from /usr/share/magic
    with open(filename) as f:
        f.seek(514)
        if f.read(4) != 'HdrS':
            return None
        f.seek(526)
        (offset,) = struct.unpack("<H", f.read(2))
        f.seek(offset+0x200)
        buf = f.read(256)
    uname, nul, rest = buf.partition('\0')
    version, spc, rest = uname.partition(' ')
    return version

def df(mnt, reserved=False):
    s = os.statvfs(mnt)
    return s.f_bsize * (s.f_bfree if reserved else s.f_bavail)

def hrsize(size, si=False, use_ib=False):
    powers = 'KMGTPEZY'
    multiple = 1000 if si else 1024
    if si:       suffix = 'B'
    elif use_ib: suffix = 'iB'
    else:        suffix = ''
    size = float(size)
    for p in powers:
        size /= multiple
        if size < multiple:
            if p in 'KM': # don't bother with sub-MB precision
                return "%u%s%s" % (int(size)+1, p, suffix)
            else:
                return "%.1f%s%s" % (size, p, suffix)

compmagic = {
    'xz':    '\xfd7zXZ',
    'lz4':   '\x02\x21',
    'gzip':  '\x1f\x8b',
    'bzip2': 'BZh',
}

def decomp_cmd(filename):
    header = open(filename, 'rb').read(6)
    for comp, magic in compmagic.items():
        if header.startswith(magic):
            return [comp, "-dc", filename]
    return ["cat", filename]

def isxen():
    '''True if this system is a xen host or guest.'''
    try:
        virttype = open("/sys/hypervisor/type").read().strip()
    except (IOError, OSError):
        virttype = "none"
    return virttype == "xen"

class TemporaryDirectory(object):
    def __init__(self, suffix="", prefix="tmp", dir=None):
        self._closed = False
        self.name = None # if mkdtemp raises an exception we'll hit __exit__
        self.name = mkdtemp(suffix, prefix, dir)

    def __enter__(self):
        return self.name

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def cleanup(self):
        if self.name and not self._closed:
            rmtree(self.name)
            self._closed = True
