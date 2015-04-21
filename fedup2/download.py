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
import librepo

from .treeinfo import Treeinfo
from .i18n import _

import logging
log = logging.getLogger("fedup.download")

# This is the template we use to generate upgrade.repo
INSTREPO_TEMPLATE = """
[instrepo]
name=Fedora $releasever - $basearch - {name}
enabled=1
metadata_expire=7d
gpgcheck=1
skip_if_unavailable=0
{urltype}={url}
gpgkey={gpgkey}
"""

DEFAULT_INSTREPO_METALINK="https://mirrors.fedoraproject.org/metalink?repo=fedora-install-$releasever&arch=$basearch"
DEFAULT_INSTREPO_GPGKEY="file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch"

class DepsolveProgressCallback(dnf.cli.output.DepSolveProgressCallBack):
    """fedup depsolving takes a while, so we need output to screen"""
    # NOTE: DNF calls this *after* it does hawkey stuff, while it's building
    # a Transaction object out of the hawkey goal results.
    # Right now (April 2015) the hawkey Python bindings don't expose
    # a callback hook for that (AFAICT).
    # So, if there's a pause before this starts.. that's what's going on.
    def __init__(self, cli):
        super(DepsolveProgressCallback, self).__init__()
        self.cli = cli
        self.count = 0
        self.total = None
        self.name = "finding updates"
        self.modecounter = dict()

    def bar(self):
        self.cli.progressbar(self.count, self.total, self.name)

    def start(self):
        super(DepsolveProgressCallback, self).start()
        self.bar()

    def pkg_added(self, pkg, mode):
        super(DepsolveProgressCallback, self).pkg_added(pkg, mode)
        if mode not in self.modecounter:
            self.modecounter[mode] = 0
        self.modecounter[mode] += 1
        if mode in ('ud','od'):
            self.count += 1
            self.bar()

    def end(self):
        super(DepsolveProgressCallback, self).end()
        if self.count != self.total:
            self.count = self.total
            self.bar()

class Downloader(object):
    def __init__(self, cli):
        self.cli = cli
        self.base = None
        self.dlprogress = None
        self.repodir = os.path.dirname(self.cli.state.statefile)
        self.get_base()

    @property
    def cachedir(self):
        return self.base.conf.cachedir

    def subst(self, rawstr):
        return dnf.conf.parser.substitute(rawstr, self.base.conf.substitutions)

    def get_base(self):
        """
        Work around a problem with dnf.Base():

        1) By default, the system $releasever is used to construct
           base.conf.cachedir - e.g. '/var/cache/dnf/x86_64/21'.
        2) If you pass a Conf object to dnf.Base(), it does not set up
           set up base.conf.cachedir - so you get just '/var/cache/dnf'.

        So here we borrow some code from dnf.Base._setup_default_conf to
        correctly set up base.conf.cachedir using our $releasever.
        """
        conf = dnf.conf.Conf()
        conf.releasever = self.cli.args.version
        self.base = dnf.Base(conf)
        conf = self.base.conf
        log.debug("before: conf.cachedir=%s", conf.cachedir)
        suffix = self.subst(dnf.const.CACHEDIR_SUFFIX)
        cache_dirs = dnf.conf.CliCache(conf.cachedir, suffix)
        conf.cachedir = cache_dirs.cachedir
        log.debug("after: conf.cachedir=%s", conf.cachedir)

    def write_instrepo(self, repofile):
        instrepo = self.cli.args.instrepo or DEFAULT_INSTREPO_METALINK
        instrepokey = self.cli.args.instrepokey or DEFAULT_INSTREPO_GPGKEY

        if not instrepo.startswith("@"):
            urltype = "baseurl"
        else:
            urltype = "metalink"
            instrepo = instrepo[1:]

        with open(repofile, "w") as outf:
            outf.write(INSTREPO_TEMPLATE.format(
                name=_("Upgrade images"),
                urltype=urltype,
                url=instrepo,
                gpgkey=instrepokey,
            ))

    def setup(self):
        # activate cachedir etc.
        self.base.activate_persistor()
        # make sure datadir exists too
        dnf.util.ensure_dir(self.cli.args.datadir)
        # write upgrade.repo
        self.write_instrepo(os.path.join(self.repodir,"upgrade.repo"))
        # make sure DNF reads our .repo file
        self.base.conf.reposdir.append(self.repodir)
        # okay, ready to read repo config
        self.base.read_all_repos()
        # TODO: expire metadata (see dnf.cli.cli.Cli._configure_repos)
        # change pkgdir to our target dir
        self.base.repos.all().pkgdir = self.cli.args.datadir
        # add progress callbacks
        self.dlprogress = dnf.cli.progress.MultiFileProgressMeter(fo=sys.stdout)
        self.base.repos.all().set_progress_bar(self.dlprogress)
        self.base.ds_callback = DepsolveProgressCallback(self.cli)
        # TODO: subclass dnf.cli.output.CliKeyImport to handle our key behavior
        #key_import = FedupCliKeyImport()
        #self.base.repos.all().set_key_import(key_import)

    def read_metadata(self):
        '''read rpmdb to find installed packages, get metadata for new pkgs.'''
        # TODO handle repos that fail to configure raising RepoError
        self.base.fill_sack(load_system_repo=True, load_available_repos=True)

    def find_upgrade_packages(self):
        '''
        Find all available upgrades.
        returns: list of package objects.
        TODO: distro-sync mode (allowing downgrades)
        '''
        installed = len(self.base.doPackageLists('installed').installed)
        self.base.ds_callback.total = installed
        # TODO: do something useful with the return values of these things
        self.base.upgrade_all()
        self.base.resolve()
        downloads = self.base.transaction.install_set
        # close connection so rpm doesn't hold SIGINT handler
        del self.base.ts
        return downloads

    def _get_handle(self, repo):
        h = repo.get_handle()
        h.destdir = self.cli.args.datadir
        h.fetchmirrors = True
        h.yumdlist = []
        h.perform()
        return h

    # FIXME needs progress meter and logging
    def _fetch_file(self, repo, relpath, local_name=None):
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
        self.base.download_packages(pkglist, self.dlprogress)
