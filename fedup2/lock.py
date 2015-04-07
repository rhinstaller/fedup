# lock.py - simple advisory file locking
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

'''
This module provides a simple interface to file locking using fcntl.lockf().

A blindingly obvious example:

    lock(fobj)
    # do some stuff with fobj
    unlock(fobj)

Or, using a context manager:

    with locked(fobj):
        # do some stuff with fobj

To ensure the file is created first:

    # NOTE: using mode "w" will truncate the file, even if it's locked!
    with locked(filename, "a+") as fobj:
        fobj.seek(0) # seek to start of file, because we used mode "a"
        # do some stuff with fobj

Note that these are *advisory* locks - they are not enforced by the kernel, and
they will have no effect on processes that aren't *also* using advisory locks.

(This means that opening a file with mode "w" or "w+" will truncate the file
*regardless* of whether or not it is locked. This is usually bad when you're
trying to share a file between processes!

This module also provides a PidLock class, which writes the current PID into
a (locked) pidfile, to keep users from running multiple copies of the same
program:

    pidlock = None
    try:
        pidlock = PidLock("/var/run/myprog.pid")
        main()
    except PidLockError as e:
        print("Already running as PID %u" % e.pid)
    finally:
        if pidlock:
            pidlock.remove()
'''

from fcntl import lockf, LOCK_UN, LOCK_EX, LOCK_SH, LOCK_NB
from os import getpid, unlink
from contextlib import contextmanager

__all__ = ['lock',
           'unlock',
           'locked',
           'LockError',
           'PidLock',
           'PidLockError']

class LockError(IOError):
    'Failed to obtain a lock.'
    def __init__(self, errno, strerror, filename, share=False):
        if share:
            strerror = "Could not obtain lock"
        else:
            strerror = "Could not obtain exclusive lock"
        IOError.__init__(self, errno, strerror, filename)

class PidLockError(LockError):
    'Failed to lock the pidfile.'
    def __init__(self, errno, strerror, filename, pid=None):
        try:
            self.pid = int(pid)
            strerror = "PID %u has lock" % self.pid
        except (TypeError, ValueError):
            self.pid = None
            strerror = "Another process has the lock"
        IOError.__init__(self, errno, strerror, filename)

def lock(fobj, block=False, share=False):
    '''
    Lock a file object using fcntl.lockf.

    If share is True, places a shared ("reader") lock.
    Multiple processes may hold shared locks for a given file.

    If share is False, places an exclusive ("writer") lock.
    Only one process may hold an exclusive lock for a given file.
    Raises IOError if the file was not opened for writing.

    If block is True, this call will block until it can take the lock.
    If block is False, raise LockError if the lock cannot be taken.

    The default is a non-blocking, exclusive lock.
    '''
    op = LOCK_SH
    if not share: op = LOCK_EX
    if not block: op |= LOCK_NB
    try:
        lockf(fobj, op)
    except (OSError, IOError) as e:
        if e.errno in (11, 13): # EACCESS or EAGAIN -> the file is locked
            raise LockError(e.errno, None, fobj.name, share)
        else:
            raise

def unlock(fobj):
    '''Unlock a file object previously locked with lockf.'''
    lockf(fobj, LOCK_UN)

@contextmanager
def locked(fobj, mode='r+', block=False, share=False):
    '''
    A context manager for locked files.
    Allows you to write things like:

    with locked(fobj): # raise LockError if fobj is locked
        # if we're here, we have fobj locked

    with locked(fobj, block=True): # wait until the file is unlocked...
        # we now have fobj locked

    with locked(filename) as fobj:
        # opens filename (with mode 'r+') and attempts to lock it as above.
        # NOTE: will raise IOError if the file doesn't exist.
    '''
    if not hasattr(fobj, 'fileno'):
        fobj = open(fobj, mode)
    lock(fobj, block=block, share=share)
    yield fobj
    unlock(fobj)

class PidLock(object):
    '''Represents a PID file which will be locked to prevent multiple
       processes from running at the same time.'''
    def __init__(self, name):
        self.name = name
        self.fobj = open(name, 'a+')
        self.fobj.seek(0)
        try:
            lock(self.fobj, share=False, block=False)
            self.fobj.truncate(0)
            self.fobj.write("%u\n" % getpid())
            self.fobj.flush()
            lock(self.fobj, share=True, block=True) # downgrade to reader-lock
        except LockError as e:
            lock(self.fobj, share=True, block=True) # wait for downgrade
            pid = self.fobj.read().strip()
            raise PidLockError(e.errno, None, e.filename, pid)

    def remove(self):
        '''Unlock and remove the pidfile.'''
        unlink(self.name)
        self.fobj.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.remove()
