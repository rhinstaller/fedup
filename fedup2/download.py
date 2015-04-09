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

class Downloader(object):
    def __init__(self, args):
        self.args = args
        self.base = None

    def setup(self):
        # create dnf object. XXX: not public API
        base = dnf.cli.cli.BaseCli()
        # prepare progress callbacks
        repobar, base.ds_callback = base.output.setup_progress_callbacks()
        # set releasever before we do anything else
        base.conf.substitutions['releasever'] = self.args.version
        # set cachedir before we start messing with repos
        if args.cachedir is not None:
            base.conf.cachedir = args.cachedir
        # ..add CACHEDIR_SUFFIX (e.g. "x86_64/21")
        # (note: the two return values are the same if you're root - if you're a
        #  regular user the first one is the user's personal cachedir)
        base.conf.cachedir, sys_cachedir = dnf.cli.cli.cachedir_fit(base.conf)
        # read repo config
        base.read_all_repos()
        # also create instrepo and add it to the repo config
        instrepo = dnf.repo.Repo('instrepo', base.conf.cachedir)
        instrepo.substitutions.update(base.conf.substitutions)
        def subst(rawstr):
            return dnf.conf.parser.substitute(rawstr, base.conf.substitutions)
        # NOTE: the progressbar will trace back if you don't set name
        instrepo.name = subst("Install Image Repo - $releasever - $basearch")
        if args.instrepo.startswith('@'):
            instrepo.metalink = subst(self.args.instrepo[1:])
        else:
            instrepo.baseurl = [subst(self.args.instrepo)]
        base.repos.add(instrepo)
        # change pkgdir to our target dir
        base.repos.all().pkgdir = args.datadir
        # add progress callback
        base.repos.all().set_progress_bar(repobar)
        # TODO: subclass dnf.cli.output.CliKeyImport to handle our key behavior
        #key_import = FedupCliKeyImport()
        #base.repos.all().set_key_import(key_import)
        self.base = base

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
        h.destdir = self.args.datadir
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
        instrepo = self.repos['instrepo']
        if self.args.nogpgcheck:
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
