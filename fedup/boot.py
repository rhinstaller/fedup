# boot - bootloader config modification code
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

from subprocess import check_output, PIPE, Popen, CalledProcessError
from shutil import copyfileobj
from util import detect_compression

kernelprefix = "/boot/vmlinuz-"

def kernelver(kernel):
    if kernel.startswith(kernelprefix):
        return kernel.split(kernelprefix,1)[1]
    else:
        raise ValueError("kernel name must start with '%s'" % kernelprefix)

def add_entry(kernel, initrd, banner=None, kargs=[], makedefault=True):
    cmd = ["/sbin/new-kernel-pkg", "--initrdfile", initrd]
    if banner:
        cmd += ["--banner", banner]
    if kargs:
        cmd += ["--kernel-args", " ".join(kargs)]
    if makedefault:
        cmd += ["--make-default"]
    cmd += ["--install", kernelver(kernel)]
    return check_output(cmd, stderr=PIPE)

def remove_entry(kernel):
    cmd = ["/sbin/new-kernel-pkg", "--remove", kernelver(kernel)]
    return check_output(cmd, stderr=PIPE)

class Initramfs(object):
    """Utility class for working with initramfs images"""
    def __init__(self, img):
        self.img = img
        self._files = None
        self._early_cpio = None
        self._compression = None
        # detect compression and/or early_cpio
        self._compression = detect_compression(self.open())
        if not self._compression:
            early = self.cpio("--extract","--to-stdout","--","early_cpio")
            if bool(early.strip()):
                self._early_cpio = True
                self._compression = detect_compression(self.open())

    def open(self):
        """Return a file-like object that provides uncompressed cpio data."""
        if self._early_cpio:
            cmd = ["/usr/lib/dracut/skipcpio", self.img]
            fobj = Popen(cmd, stdout=PIPE, stderr=PIPE).stdout
        else:
            fobj = open(self.img, 'rb')

        if self._compression:
            cmd = [self._compression, "-dc"]
            return Popen(cmd, stdin=fobj, stdout=PIPE, stderr=PIPE).stdout
        else:
            return fobj

    def cpio(self, *args, **kwargs):
        """Run cpio on the img with the given arguments, transparently
           decompressing if needed.
           If cwd is not None, chdir to that dir before running cpio."""
        cwd = kwargs.get("cwd")
        return check_output(("cpio", "--quiet") + args, cwd=cwd,
                            stdin=self.open())

    def listfiles(self):
        """List the contents of the image."""
        if self._files is None:
            self._files = self.cpio("--list").splitlines()
        return self._files

    def extract(self, files, root=None):
        """Extract the listed files into the given root dir (or cwd)"""
        self.cpio("-iumd", *files, cwd=root)

    def append(self, files, root=None):
        '''Append the given files to the named initramfs.
           Raises CalledProcessError if cpio returns a non-zero exit code.'''
        if isinstance(files, basestring):
            files = [files]
        if root is None:
            root = ''
        filelist = ''.join(f+'\n' for f in files if os.path.exists(root+'/'+f))
        with open(self.img, 'ab') as outfd:
            cmd = ["cpio", "-co"]
            cpio = Popen(cmd, stdin=PIPE, stdout=outfd, stderr=PIPE, cwd=root)
            (out, err) = cpio.communicate(input=filelist)
            if cpio.returncode:
                raise CalledProcessError(cpio.returncode, cmd, err)

    def append_images(self, images):
        '''Append the given images to the named initramfs.
           Raises IOError if the files can't be read/written.'''
        with open(self.img, 'ab') as outfd:
            for i in images:
                with open(i, 'rb') as infd:
                    copyfileobj(infd, outfd)

    # support "if filename in initramfs", "for filename in initramfs"
    def __contains__(self, item):
        return (item in self.listfiles())
    def __iter__(self):
        return iter(self.listfiles())
    iterkeys = __iter__

def find_initramfs(kernel_ver):
    """
    Determine the initramfs path for the given kernel version, either
    /boot/$MACHINE_ID/$KERNEL_VER/initrd (if it exists) or
    /boot/initramfs-$KERNEL_VER.img (the traditional version).

    See http://freedesktop.org/wiki/Specifications/BootLoaderSpec for details.
    """
    try:
        machine_id = open("/etc/machine-id").readline().strip()
        img = "/boot/%s/%s/initrd" % (machine_id, kernel_ver)
    except IOError:
        img = ""

    if os.path.exists("/boot/loader/entries") and os.path.exists(img):
        return img
    else:
        return "/boot/initramfs-%s.img" % kernel_ver

def current_initramfs():
    """Return the path to the initramfs for the running kernel."""
    return find_initramfs(os.uname()[2])
