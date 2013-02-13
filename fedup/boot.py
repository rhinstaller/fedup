# fedup.boot - bootloader config modification code for the Fedora Upgrader
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

from subprocess import check_output, PIPE, Popen, CalledProcessError

kernelprefix = "/boot/vmlinuz-"

def kernelver(kernel):
    if kernel.startswith(kernelprefix):
        return kernel.split(kernelprefix,1)[1]
    else:
        raise ValueError("kernel name must start with '%s'" % kernelprefix)

def add_entry(kernel, initrd, banner=None, kargs=[], makedefault=True):
    cmd = ["new-kernel-pkg", "--initrdfile", initrd]
    if banner:
        cmd += ["--banner", banner]
    if kargs:
        cmd += ["--kernel-args", " ".join(kargs)]
    if makedefault:
        cmd += ["--make-default"]
    cmd += ["--install", kernelver(kernel)]
    return check_output(cmd, stderr=PIPE)

def remove_entry(kernel):
    cmd = ["new-kernel-pkg", "--remove", kernelver(kernel)]
    return check_output(cmd, stderr=PIPE)

def initramfs_append(initramfs, files):
    '''Append the given files to the named initramfs.
       Raises IOError if the files can't be read/written.
       Raises CalledProcessError if cpio returns a non-zero exit code.'''
    if isinstance(files, basestring):
        files = [files]
    filelist = ''.join(f+'\n' for f in files if open(f))
    with open(initramfs, 'ab') as outfd:
        cmd = ["cpio", "-co"]
        cpio = Popen(cmd, stdin=PIPE, stdout=outfd, stderr=PIPE)
        (out, err) = cpio.communicate(input=filelist)
        if cpio.returncode:
            raise CalledProcessError(cpio.returncode, cmd, err)
