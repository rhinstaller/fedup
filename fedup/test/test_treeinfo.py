from . import unittest, mock, my_mock_open

from treeinfo import *

# first some helper data/functions

import hashlib
def quickhash(algo, data):
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest()

filelist = (
    'LiveOS/squashfs.img',
    'images/pxeboot/vmlinuz',
    'images/pxeboot/initrd.img',
    'images/boot.iso',
    'images/macboot.img',
    'images/efiboot.img',
    'repodata/repomd.xml',
)

# pick some random-ish placeholder data for each file
filedata = {f:"PLACEHOLDER DATA FOR %s\n" % f.upper() for f in filelist}

# known-good config file data
configdata = '''\
[general]
family = Fedora
timestamp = 1337720130.41
variant = Fedora
version = 17
packagedir = 
arch = x86_64

[stage2]
mainimage = LiveOS/squashfs.img

[images-x86_64]
kernel = images/pxeboot/vmlinuz
initrd = images/pxeboot/initrd.img
boot.iso = images/boot.iso

[images-xen]
kernel = images/pxeboot/vmlinuz
initrd = images/pxeboot/initrd.img

[checksums]
'''

# add the file hashes to the checksums section
algo = 'sha256'
filehashes = {f:quickhash(algo,data) for f,data in filedata.items()}
for name, filehash in filehashes.items():
    configdata += '{} = {}:{}\n'.format(name, algo, filehash)

from contextlib import contextmanager

@contextmanager
def mock_image_file(name, data):
    mock_open = my_mock_open(read_data=data)
    with mock.patch('treeinfo.open', mock_open, create=True) as m:
        yield m
        m.assert_called_once_with(name, 'rb')
        assert m().read.called

# and now, the tests!

class TreeinfoBasicTest(unittest.TestCase):
    def setUp(self):
        self.t = Treeinfo()
        self.t.read_str(configdata)

    def test_checkvalues(self):
        self.t.checkvalues()

    def test_image_arches(self):
        self.assertEqual(self.t.image_arches(), ['x86_64','xen'])

    def test_get(self):
        self.assertEqual(self.t.get('stage2', 'mainimage'),
                                    'LiveOS/squashfs.img')

    def test_get_image(self):
        self.assertEqual(self.t.get_image('x86_64', 'boot.iso'),
                                          'images/boot.iso')

    def mock_hexdigest(self, name, data):
        mock_open = my_mock_open(read_data=data)
        with mock.patch('treeinfo.open', mock_open, create=True) as m:
            rv = self.t.checkfile('dummyfile', name)
            m.assert_called_once_with('dummyfile', 'rb')
            fd = m.return_value
            self.assertTrue(fd.read.called)

    def mock_checkfile(self, name, data):
        mock_open = my_mock_open(read_data=data)
        with mock.patch('treeinfo.open', mock_open, create=True) as m:
            rv = self.t.checkfile('dummyfile', name)
            m.assert_called_once_with('dummyfile', 'rb')
            fd = m.return_value
            self.assertTrue(fd.read.called)
        return rv

    def test_checkfile_ok(self):
        for name in filelist:
            self.assertTrue(self.mock_checkfile(name, filedata[name]))

    def test_checkfile_bad(self):
        self.assertFalse(self.mock_checkfile(filelist[0],'OH BALLS, BAD DATA'))

    def test_setopt(self):
        self.t.setopt("bonk", "clonk", "flap")
        self.assertEqual(self.t.get("bonk", "clonk"), "flap")

class AddImageTest(unittest.TestCase):
    def setUp(self):
        self.t = Treeinfo()
        self.t.read_str(configdata)
        self.arch = 'fakearch'
        self.itype = 'fake.iso'
        self.ipath = 'images/fake.iso'
        self.sums = set(self.t.items('checksums'))
        self.arches = set(self.t.image_arches())
        self.sections = set(self.t.sections())
        with mock_image_file(self.ipath, data=configdata.upper()):
            self.t.add_image(self.arch, self.itype, self.ipath)

    def test_get_image(self):
        self.assertEqual(self.t.get_image(self.arch, self.itype), self.ipath)

    def test_sections(self):
        newsections = self.sections.symmetric_difference(self.t.sections())
        self.assertEqual(newsections, set(['images-'+self.arch]))

    def test_checksum_count(self):
        newitems = self.sums.symmetric_difference(self.t.items('checksums'))
        newval = self.t.get('checksums', self.ipath)
        self.assertEqual(newitems, set([(self.ipath, newval)]))

    def test_checkfile(self):
        with mock_image_file('dummyfile', data=configdata.upper()):
            self.assertTrue(self.t.checkfile('dummyfile', self.ipath))
