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

import os, unittest
from tempfile import mkdtemp
from shutil import rmtree

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from fedup2.treeinfo import *

treeinfo_test_str = """
[general]
family = Test
timestamp = 1428424187.57
variant = Tickle
version = 2903
packagedir =
arch = x86_64

[images-x86_64]
kernel = images/pxeboot/vmlinuz
initrd = images/pxeboot/initrd.img

[checksums]
images/pxeboot/initrd.img = sha256:4c58e80674ec670d177a2bb81f1854d423bdb7c38c2bf212f7c070a007278925
images/pxeboot/vmlinuz = sha256:168e65bcea301788aa64add471df6812ed8076453ab476eda673cbf428ce240a
"""

# NOTE: the above sha256sums correspond to the data below, so keep them synched
test_repo_files = {
    '.treeinfo':treeinfo_test_str,
    'images/pxeboot/vmlinuz':'THIS IS A FAKE KERNEL IMAGE',
    'images/pxeboot/initrd.img':'THIS IS A FAKE INITRAMFS',
    'images/fake/test.img':'HELLO MY NAME IS FAKE IMAGE',
}

class TestTreeinfoBasic(unittest.TestCase):
    def setUp(self):
        self.ti = Treeinfo(StringIO(treeinfo_test_str))

    def test_read_str(self):
        """treeinfo: test read_str()"""
        self.ti.read_str(treeinfo_test_str)
        self.assertEqual(self.ti.get("general","timestamp"), "1428424187.57")
        self.assertEqual(self.ti.get("general","packagedir").strip(), "")

    def test_setopt(self):
        """treeinfo: test setopt()"""
        self.ti.setopt("wizard", "hat", "pointy")
        self.assertEqual(self.ti.get("wizard", "hat"), "pointy")

    def test_image_arches(self):
        """treeinfo: test image_arches()"""
        self.assertEqual(self.ti.image_arches(), ["x86_64"])

    def test_checkvalues_ok(self):
        """treeinfo: test checkvalue() on valid data"""
        self.ti.checkvalues()

    def test_checkvalues_failure(self):
        """treeinfo: checkvalue() raises TreeinfoError on bad data"""
        ti = Treeinfo(StringIO(treeinfo_test_str))
        ti.remove_option("general", "version")
        with self.assertRaises(TreeinfoError):
            ti.checkvalues()

    def test_get_image(self):
        """treeinfo: test get_image()"""
        self.assertEqual(self.ti.get_image("x86_64", "kernel"),
                         "images/pxeboot/vmlinuz")

# TODO: we could probably use some Mock files here instead
def populate_dir(filedict):
    '''helper function for making a repo.'''
    tmpdir = mkdtemp(prefix=__name__+'.')
    for relpath, filedata in filedict.items():
        fullpath = os.path.join(tmpdir, relpath)
        try:
            os.makedirs(os.path.dirname(fullpath))
        except OSError as e:
            if e.errno != 17:
                raise
        with open(fullpath, "w") as outf:
            outf.write(filedata)
    return tmpdir

class TestTreeinfoWithDir(unittest.TestCase):
    def setUp(self):
        self.topdir = populate_dir(test_repo_files)
        self.fromfile = os.path.join(self.topdir, ".treeinfo")
        self.ti = Treeinfo(fromfile=self.fromfile, topdir=self.topdir)
        self.img_rel = 'images/fake/test.img'
        self.img_path = os.path.join(self.topdir, self.img_rel)
        self.kernel_rel = self.ti.get_image('x86_64','kernel')
        self.kernel_path = os.path.join(self.topdir, self.kernel_rel)

    def tearDown(self):
        rmtree(self.topdir)

    def test_checkfile_ok(self):
        """treeinfo: test checkfile() on good data"""
        self.assertTrue(self.ti.checkfile(self.kernel_path, self.kernel_rel))

    def test_checkfile_bad(self):
        """treeinfo: test checkfile() on bad data"""
        with open(self.kernel_path, "a") as outf:
            outf.write("\nLOL HAXED")
        self.assertFalse(self.ti.checkfile(self.kernel_path, self.kernel_rel))

    def test_checkfile_missing(self):
        """treeinfo: checkfile() raises IOError on a missing file"""
        os.unlink(self.kernel_path)
        with self.assertRaises(IOError):
            self.ti.checkfile(self.kernel_path, self.kernel_rel)

    def test_checkfile_nosum(self):
        """treeinfo: checkfile() raises TreeinfoError with missing checksum"""
        with self.assertRaises(TreeinfoError):
            self.ti.checkfile(self.img_path, self.img_rel)

    def test_checkfile_bad_algo(self):
        """treeinfo: checkfile() raises TreeinfoError with bad algorithm"""
        self.ti.set('checksums', self.kernel_rel, 'pork:xxxxxxx')
        with self.assertRaises(TreeinfoError):
            self.ti.checkfile(self.kernel_path, self.kernel_rel)

    def test_checkfile_bad_sum(self):
        """treeinfo: checkfile() raises TreeinfoError with malformed checksum"""
        self.ti.set('checksums', self.kernel_rel, 'sha256:c0ffee')
        with self.assertRaises(TreeinfoError):
            self.ti.checkfile(self.kernel_path, self.kernel_rel)

    def test_add_checksum(self):
        """treeinfo: test add_checksum()"""
        self.ti.add_checksum(self.img_rel)
        self.assertTrue(self.ti.checkfile(self.img_path, self.img_rel))

    def test_add_image(self):
        """treeinfo: test add_image()/add_checksum()"""
        self.ti.add_image('fakearch','initrd', self.img_rel)
        self.assertEqual(self.ti.get_image('fakearch','initrd'), self.img_rel)
        self.assertTrue(self.ti.checkfile(self.img_path, self.img_rel))

    def test_add_timestamp(self):
        """treeinfo: test add_timestamp()"""
        import time
        ts = time.time()
        self.assertNotEqual(float(self.ti.get('general','timestamp')), ts)
        self.ti.add_timestamp(ts)
        self.assertEqual(float(self.ti.get('general','timestamp')), ts)

    def test_writetreeinfo(self):
        """treeinfo: test writetreeinfo()"""
        self.ti.add_image('fakearch','initrd',self.img_rel)
        self.ti.writetreeinfo()
        newti = Treeinfo(fromfile=self.fromfile, topdir=self.topdir)
        for s in newti.sections():
            self.assertTrue(self.ti.has_section(s))
            for k, v in self.ti.items(s):
                newv = newti.get(s,k)
                self.assertEqual(v, newv)
        newti.add_timestamp()
        self.assertTrue(float(self.ti.get('general','timestamp')) <
                        float(newti.get('general','timestamp')))

    def test_read_garbage(self):
        """treeinfo: raise TreeinfoError on malformed file"""
        with open(self.fromfile, "w") as fobj:
            fobj.write("OH YEAHHHHHHHH\n")
        with self.assertRaises(TreeinfoError):
            newti = Treeinfo(self.fromfile)
