#!/usr/bin/python

from subprocess import check_output, CalledProcessError, PIPE
from collections import namedtuple

GrubbyEntry = namedtuple("GrubbyEntry", "index kernel args root initrd title")

class Grubby(object):
    '''View/manipulate bootloader configuration using `grubby`.'''

    bootloaders = ("grub", "grub2", "elilo", "extlinux",
                   "lilo", "silo", "yaboot", "zipl")

    def __init__(self, config=None, bootloader=None):
        self.config = config
        self.bootloader = bootloader

        if bootloader and bootloader not in self.bootloaders:
            raise ValueError("bootloader must be one of: %s" % \
                                " ".join(self.bootloaders))

    def _grubby(self, *args):
        cmd = ["grubby"]
        if self.bootloader:
            cmd += ["--%s" % bootloader]
        if self.config:
            cmd += ["--config-file", config]
        return check_output(cmd + [str(a) for a in args], stderr=PIPE)

    def get_entry(self, index):
        '''Returns a GrubbyEntry for the entry at the given index.'''
        index = int(index) # make sure index is int
        out = self._grubby("--info", index)
        info = dict()
        for line in out.split("\n"):
            k, eq, val = line.partition('=')
            if k and val:
                if k == 'index':
                    info[k]=int(val)
                else:
                    info[k]=val
        return GrubbyEntry(**info)

    def get_entries(self):
        ents = []
        for n in xrange(64): # an arbitrary but reasonable limit
            try:
                ents.append(self.get_entry(n))
            except CalledProcessError:
                break
        return ents

    def default_index(self):
        return int(self._grubby("--default-index"))

    def default_entry(self):
        return self.get_entry(self.default_index())

    def set_default_entry(self, index):
        index = int(index) # make sure index is int
        self._grubby("--set-default", index)

    def add_entry(self, kernel, initrd, title,
                        args=None, copydefault=True, makedefault=False):
        '''
        Add a boot entry with the given parameters.
        If copydefault is True, 'args' will be appended to the args from
        the current default entry.
        If makedefault is True, the new entry will be made the default.
        '''
        grubby_args = ["--add-kernel", kernel, "--title", title]
        if initrd:
            grubby_args += ["--initrd", initrd]
        if args:
            grubby_args += ["--args", args]
        if copydefault:
            grubby_args += ["--copy-default"]
        if makedefault:
            grubby_args += ["--make-default"]
        self._grubby(*grubby_args)

    def update_entry(self, index, add_args=None, remove_args=None):
        '''
        Note that update_entry currently cannot modify anything except the
        boot args; if you need to change the title etc. you will probably
        need to create a new entry and delete the old one.
        '''
        index = int(index) # make sure index is int
        grubby_args = ["--update-kernel", str(index)]
        if add_args:
            grubby_args += ["--args", add_args]
        if remove_args:
            grubby_args += ["--remove-args", remove_args]
        self._grubby(*grubby_args)

    def remove_entry(self, index):
        index = int(index) # make sure index is int
        self._grubby("--remove-kernel", index)

