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
from subprocess import Popen, CalledProcessError, PIPE, STDOUT
from pipes import quote as shellquote
import logging
log = logging.getLogger('fedup.util')

import logging
log = logging.getLogger(__package__+".util")

try:
    from ctypes import cdll, c_bool
    selinux = cdll.LoadLibrary("libselinux.so.1")
    is_selinux_enabled = selinux.is_selinux_enabled
    is_selinux_enabled.restype = c_bool
except (ImportError, AttributeError, OSError):
    is_selinux_enabled = lambda: False

def call_output(cmd, *pargs, **kwargs):
    log.info("exec: `%s`", ' '.join(shellquote(a) for a in cmd))
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, *pargs, **kwargs)
    (out, err) = p.communicate()
    retcode = p.poll()
    return (retcode, out, err)

def call(cmd, *pargs, **kwargs):
    return call_output(cmd, *pargs, **kwargs)[0]

def check_output(cmd, *pargs, **kwargs):
    (retcode, out, err) = call_output(cmd, *pargs, **kwargs)
    if retcode:
        raise CalledProcessError(retcode, cmd, output=out)
    return out

def check_call(cmd, *pargs, **kwargs):
    check_output(cmd, *pargs, **kwargs)
    return 0

def listdir(d):
    for f in os.listdir(d):
        yield os.path.join(d, f)

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
    rm_f(d, rm=rmtree)

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
