#!/usr/bin/python

from distutils.core import setup, Command

import os
from os.path import join
from subprocess import check_call

class Gettext(Command):
    description = "Use po/POTFILES.in to generate po/<name>.pot"
    user_options = []
    def initialize_options(self):
        self.encoding = 'UTF-8'
        self.po_dir = 'po'
        self.add_comments = True

    def finalize_options(self):
        pass

    def _xgettext(self, opts):
        name = self.distribution.get_name()
        version = self.distribution.get_version()
        email = self.distribution.get_author_email()
        cmd = ['xgettext', '-j', '--default-domain', name, '--package-name', name,
               '--package-version', version, '--msgid-bugs-address', email,
               '--output', join(self.po_dir, name + '.pot')]
        if self.add_comments:
            cmd.append('--add-comments')
        check_call(cmd + opts)

    def run(self):
        self._xgettext(['--language=Python', '-f', 'po/POTFILES.in'])

class Msgfmt(Command):
    description = "Generate po/*.mo from po/*.po"
    user_options = []
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        po_dir = 'po'
        for po in os.listdir(po_dir):
            po = join(po_dir, po)
            if po.endswith('.po'):
                mo = po[:-3]+'.mo'
                check_call(['msgfmt', '-vv', po, '-o', mo])

setup(name="fedup",
      version="0.1",
      description="Fedora Upgrade",
      long_description="",
      author="Will Woods",
      author_email="wwoods@redhat.com",
      url="https://github.com/wgwoods/fedup",
      download_url="https://github.com/wgwoods/fedup/downloads",
      license="GPLv2+",
      packages=["fedup"],
      scripts=["fedup-cli"],
      cmdclass={
        'gettext': Gettext,
        'msgfmt': Msgfmt,
        }
      )
