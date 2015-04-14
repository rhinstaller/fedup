# test_state.py - tests for fedup.state
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

import unittest
from ..state import *

from tempfile import mkstemp
import os

class TestStateBasic(unittest.TestCase):
    def setUp(self):
        State.statefile = ''
        self.state = State()

    def test_set(self):
        '''state: test setting a property'''
        k = "wow this is totally a kernel path"
        self.state.kernel = k
        self.assertEqual(self.state._conf.get("upgrade", "kernel"), k)

    def test_get(self):
        '''state: test getting a property'''
        self.state._conf.add_section("upgrade")
        self.state._conf.set("upgrade", "kernel", "A VERY COOL VALUE")
        self.assertEqual(self.state.kernel, "A VERY COOL VALUE")

    def test_get_missing(self):
        '''state: getting property with missing config item returns None'''
        self.assertTrue(self.state.kernel is None)

    def test_del(self):
        '''state: test deleting a property'''
        self.state.initrd = "doomed"
        del self.state.initrd
        self.assertTrue(self.state.initrd is None)
        self.assertFalse(self.state._conf.has_option("upgrade", "initrd"))

    def test_cmdline(self):
        '''state: test the cmdline property'''
        argv = ['/usr/bin/cowsay', '-e\tx', '-T\'\'', 'i am made of meat']
        self.state.cmdline = argv
        self.assertEqual(self.state.cmdline, argv)

    def test_cmdline_missing(self):
        '''state: missing cmdline also returns None'''
        self.assertEqual(self.state.cmdline, None)

    def test_summarize(self):
        '''state: make sure summarize() works'''
        target = "TacOS 4u"
        self.assertFalse(target in self.state.summarize())
        # if we have a target, the summary should mention it
        self.state.upgrade_target = target
        inprog_msg = self.state.summarize()
        self.assertTrue(target in inprog_msg)
        # different messages for in-progress vs. ready-to-go
        self.state.upgrade_ready = 1
        self.assertTrue(target in self.state.summarize())
        self.assertNotEqual(self.state.summarize(), inprog_msg)
        # if we're now unready again, we should have the in-progress message
        del self.state.upgrade_ready
        self.assertEqual(self.state.summarize(), inprog_msg)

class TestStateWithFile(unittest.TestCase):
    def setUp(self):
        # TODO it'd probably be better to use a mock file here
        _, self.tmpfile = mkstemp(prefix='state.')
        State.statefile = self.tmpfile
        self.state = State()

    def _read_data(self):
        return open(self.tmpfile).read()

    def tearDown(self):
        os.unlink(self.tmpfile)

    def test_write(self):
        '''state: test State.write()'''
        self.state.datadir = "/data"
        self.state.write()
        data = self._read_data()
        self.assertEqual(data.strip(), '[download]\ndatadir = /data')

    def test_context(self):
        '''state: test State as context manager'''
        target = "TacOS 4u"
        with self.state as state:
            self.state.upgrade_target = target
        newstate = State()
        self.assertEqual(newstate.upgrade_target, target)

    def test_clear(self):
        '''state: test State.clear()'''
        kernelname = "tacos"
        with self.state as state:
            self.state.boot_name = kernelname
        self.state = State()
        self.assertEqual(self.state.boot_name, kernelname)
        with self.state as state:
            state.clear()
        newstate = State()
        self.assertEqual(self._read_data(), '')
