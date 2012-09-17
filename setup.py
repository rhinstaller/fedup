#!/usr/bin/python

from distutils.core import setup

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
      )
