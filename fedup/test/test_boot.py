from . import unittest, mock, my_mock_open

import boot

kernelver = 'fedup.test'
kernel = '/boot/vmlinuz-{}'.format(kernelver)
initrd = '/boot/initramfs-{}.img'.format(kernelver)

class BootAddRemoveTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch('boot.check_output')
        self.check_output = patcher.start()
        self.addCleanup(patcher.stop)

    def test_add_entry(self):
        boot.add_entry(kernel, initrd)
        assert self.check_output.called_once_with(['new-kernel-pkg',
                '--initrdfile', initrd,
                '--make-default',
                '--install', kernelver])

    def test_add_entry_banner(self):
        banner = 'FEDUP!!! YESSSSSS'
        boot.add_entry(kernel, initrd, banner=banner)
        assert self.check_output.called_once_with(['new-kernel-pkg',
                '--initrdfile', initrd,
                '--banner', banner,
                '--make-default',
                '--install', kernelver])

    def test_remove_entry(self):
        boot.remove_entry(kernel)
        assert self.check_output.called_once_with(['new-kernel-pkg',
                '--remove', kernelver])

class NeedMdadmConfTest(unittest.TestCase):
    def need_mdadm_conf(self, data='', exists=True):
        mock_open = my_mock_open(read_data=data, exists=exists)
        with mock.patch('boot.open', mock_open, create=True) as m:
            rv = boot.need_mdadmconf()
            m.assert_called_once_with('/etc/mdadm.conf')
            self.assertTrue(exists == m.return_value.__iter__.called)
        return rv

    def test_no_file(self):
        self.assertFalse(self.need_mdadm_conf(exists=False))

    def test_empty_file(self):
        self.assertFalse(self.need_mdadm_conf(''))

    def test_comments_only(self):
        self.assertFalse(self.need_mdadm_conf('''
            # this is a fake mdadm.conf
            # there's a whole bunch of comments here

            # but there's no real commands or data
            '''))

    def test_actual_data(self):
        self.assertTrue(self.need_mdadm_conf('''
            # this is a fake mdadm.conf
            # there's a whole bunch of comments here
            # and also empty lines like this

            # but way down here there's a single command
            ABIDE

            # and then more comments
            '''))
