# download.py - DNF-based downloader, for doin' upgrades
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

import os
import sys
import dnf
import dnf.cli
import dnf.util

import logging
log = logging.getLogger("fedup.download")

class Downloader(object):
    def __init__(self, cli):
        self.cli = cli
        self.base = None

    @property
    def cachedir(self):
        return self.base.conf.cachedir

    def subst(self, rawstr):
        return dnf.conf.parser.substitute(rawstr, self.base.conf.substitutions)

    def fix_cachedir(self):
        conf = self.base.conf
        log.debug("before: conf.cachedir=%s", conf.cachedir)
        # This comes from dnf.base.Base._setup_default_conf()
        suffix = self.subst(dnf.const.CACHEDIR_SUFFIX)
        cache_dirs = dnf.conf.CliCache(conf.cachedir, suffix)
        conf.cachedir = cache_dirs.cachedir
        log.debug("after: conf.cachedir=%s", conf.cachedir)

    def add_repo(self, repoid, url):
        repo = dnf.repo.Repo(repoid, self.base.conf.cachedir)
        repo.substitutions.update(self.base.conf.substitutions)
        # NOTE: the progressbar will trace back if you don't set name
        if repoid == 'instrepo':
            repo.name = self._subst("Install Repo - $basearch/$releasever")
        if url.startswith('@'):
            repo.metalink = self.subst(url[1:])
        else:
            repo.baseurl = [self.subst(url)]
        self.base.repos.add(repo)

    def setup(self):
        # start with empty Conf or else dnf sets up cachedir wrong
        conf = dnf.conf.Conf()
        # set releasever before we do anything else
        conf.releasever = self.cli.args.version
        # create dnf object. XXX: BaseCli is not part of the public API..
        base = dnf.cli.cli.BaseCli(conf)
        self.base = base
        # set up and activate cachedir
        self.fix_cachedir()
        base.activate_persistor()
        # make sure datadir exists too
        dnf.util.ensure_dir(self.cli.args.datadir)
        # prepare progress callbacks
        repobar, base.ds_callback = base.output.setup_progress_callbacks()
        # read repo config
        base.read_all_repos()
        # add repos from commandline
        for action, value in self.cli.args.repos:
            if action == 'add':
                repoid, url = value.split("=", 1)
                self.add_repo(repoid, url)
            # FIXME: enable, disable, gpgkey
        # change pkgdir to our target dir
        base.repos.all().pkgdir = self.cli.args.datadir
        # add progress callback
        base.repos.all().set_progress_bar(repobar)
        # TODO: subclass dnf.cli.output.CliKeyImport to handle our key behavior
        #key_import = FedupCliKeyImport()
        #self.base.repos.all().set_key_import(key_import)

    def check_repos(self):
        # TODO: check for other Important Repos, list disabled repos, etc.
        try:
            self.base.repos['instrepo']
        except KeyError:
            self.cli.error("no instrepo??")

    def read_metadata(self):
        '''read rpmdb to find installed packages, get metadata for new pkgs.'''
        # TODO handle repos that fail to configure
        self.base.fill_sack(load_system_repo=True, load_available_repos=True)

    def find_upgrade_packages(self):
        '''
        Find all available upgrades.
        returns: list of package objects.
        TODO: distro-sync mode (allowing downgrades)
        '''
        rv = self.base.upgrade_all()
        ok = self.base.resolve()
        # XXX:should we do something with ok and rv?
        return self.base.transaction.install_set

    @staticmethod
    def _get_handle(self, repo):
        h = repo.get_handle()
        h.destdir = self.cli.args.datadir
        h.fetchmirrors = True
        h.yumdlist = []
        h.perform()
        return h

    # FIXME needs progress meter and logging
    def _fetch_file(repo, relpath, local_name=None):
        handle = self._get_handle(repo)
        if local_name is None:
            local_name = os.path.basename(relpath)
        fullpath = os.path.join(handle.destdir, local_name)
        with open(fullpath, "w+") as f:
            librepo.download_url(relpath, f.fileno(), handle)
        return fullpath

    def download_images(self):
        '''Download boot images from the 'instrepo' repo.
        returns two file paths: (kernel, initrd)'''
        instrepo = self.base.repos['instrepo']
        if self.cli.args.nogpgcheck:
            treeinfo_file = self._fetch_file(instrepo, ".treeinfo")
        else:
            treeinfo_signed = self._fetch_file(instrepo, ".treeinfo.signed")
            treeinfo_file = treeinfo_signed[:-7] # drop ".signed"
            # FIXME: verify treeinfo_signed, write plaintext to treeinfo_file
            raise NotImplementedError
        ti = Treeinfo(treeinfo_file)
        arch = instrepo.substitutions['basearch']
        kernel = self._fetch_file(instrepo, ti.get_image(arch, 'kernel'))
        initrd = self._fetch_file(instrepo, ti.get_image(arch, 'upgrade'))
        # FIXME checking needs to be better here
        assert ti.checkfile(kernel, ti.get_image(arch, 'kernel'))
        assert ti.checkfile(initrd, ti.get_image(arch, 'upgrade'))

    def download_packages(self, pkglist):
        dlprogress = dnf.cli.progress.MultiFileProgressMeter(fo=sys.stdout)
        self.base.download_packages(pkglist, progress=dlprogress)
