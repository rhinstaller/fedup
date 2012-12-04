# fedup.download - yum-based download/depsolver for Fedora Upgrade
#
# Copyright (C) 2012 Red Hat Inc.
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
import yum
import logging
import fedup.boot as boot
from shutil import copy2
from selinux import is_selinux_enabled
from fedup.callback import BaseTsCallback
from fedup.treeinfo import Treeinfo, TreeinfoError
from fedup.conf import Config
from yum.Errors import YumBaseError

enabled_plugins = ['blacklist', 'whiteout']
disabled_plugins = ['rpm-warm-cache', 'remove-with-leaves', 'presto',
                    'auto-update-debuginfo', 'refresh-packagekit']

cachedir="/var/tmp/fedora-upgrade"
upgrade_target_wants = "/lib/systemd/system/system-upgrade.target.wants"

from fedup import _
from fedup import packagedir, packagelist, upgradeconf
from fedup import upgradelink, upgraderoot, kernelpath, initrdpath
from fedup import default_install_mirrorlist
from fedup.media import write_systemd_unit
from fedup.util import listdir, mkdir_p, rm_f, rm_rf

log = logging.getLogger("fedup.yum") # XXX kind of misleading?

class FedupDownloader(yum.YumBase):
    '''Yum-based downloader class for fedup. Based roughly on AnacondaYum.'''
    def __init__(self, version=None, cachedir=cachedir, cacheonly=False):
        # TODO: special handling for version='test' where we just synthesize
        #       a bunch of fake RPMs with interesting properties
        log.info("FedupDownloader(version=%s, cachedir=%s)", version, cachedir)
        yum.YumBase.__init__(self)
        self.use_txmbr_in_callback = True
        self.preconf.debuglevel = -1
        self.preconf.enabled_plugins = enabled_plugins
        self.preconf.disabled_plugins = disabled_plugins
        if version:
            self.preconf.releasever = version
        self.cacheonly = cacheonly
        self.prerepoconf.cachedir = cachedir
        self.prerepoconf.cache = cacheonly
        log.debug("prerepoconf.cache=%i", self.prerepoconf.cache)
        self.instrepoid = None
        self.disabled_repos = []
        self._treeinfo = None
        if version is None: # i.e. no --network arg
            self.repos.disableRepo('*')
        # TODO: locking to prevent multiple instances
        # TODO: override logging objects so we get yum logging

    def _getConfig(self):
        firstrun = hasattr(self, 'preconf')
        conf = yum.YumBase._getConfig(self)
        if firstrun:
            # override some of yum's defaults
            conf.disable_excludes = ['all']
            conf.cache = self.cacheonly
            log.debug("conf.cache=%i", conf.cache)
        return conf

    def setup_repos(self, callback=None, progressbar=None, repos=[]):
        '''Return a list of repos that had problems setting up.'''
        # FIXME invalidate cache if the version doesn't match previous version
        log.info("checking repos")

        if self.instrepoid is None:
            # network install, no instrepo provided, try the default mirrorlist
            self.instrepoid = 'default-installrepo'
            self.add_enable_repo(self.instrepoid, variable_convert=True,
                                 mirrorlist=default_install_mirrorlist)
            # XXX NOTE this doesn't work yet because the Fedora Infrastructure
            # guys haven't set up default_install_mirrorlist yet.

        # commandline overrides for the enabled/disabled repos
        # NOTE: will raise YumBaseError if there are problems
        for action, repo in repos:
            if action == 'enable':
                self.repos.enableRepo(repo)
            elif action == 'disable':
                self.repos.disableRepo(repo)
            elif action == 'add':
                (repoid, url) = repo.split('=',1)
                self.add_enable_repo(repoid, [url], variable_convert=True)

        # set up callbacks etc.
        self.repos.setProgressBar(progressbar)
        self.repos.callback = callback

        # check repos
        for repo in self.repos.listEnabled():
            try:
                md_types = repo.repoXML.fileTypes()
            except yum.Errors.RepoError:
                log.info("can't find valid repo metadata for %s", repo.id)
                repo.disable()
                self.disabled_repos.append(repo.id)
            else:
                log.info("repo %s seems OK" % repo.id)

        log.debug("repos.cache=%i", self.repos.cache)

        return self.disabled_repos

    # XXX currently unused
    def save_repo_configs():
        '''save repo configuration files for later use'''
        repodir = os.path.join(cachedir, 'yum.repos.d')
        mkdir_p(repodir)
        for repo in self.repos.listEnabled():
            repofile = os.path.join(repodir, "%s.repo" % repo.id)
            try:
                repo.write(open(repofile), 'w')
            except IOError as e:
                log.warn("couldn't write repofile for %s: %s", repo.id, str(e))

    # NOTE: could raise RepoError if metadata is missing/busted
    def build_update_transaction(self, callback=None):
        log.info("looking for updates")
        self.dsCallback = callback
        self.update()
        (rv, msgs) = self.buildTransaction(unfinished_transactions_check=False)
        log.info("buildTransaction returned %i", rv)
        for m in msgs:
            log.info("    %s", m)
        # NOTE: we ignore errors, as anaconda did before us.
        self.dsCallback = None
        return [t.po for t in self.tsInfo.getMembers()
                     if t.ts_state in ("i", "u")]

    def download_packages(self, pkgs, callback=None):
        # Verifying a full upgrade payload of ~2000 pkgs takes a good 90-120
        # seconds with no callback. Unacceptable!
        # So: here we have our own verifyPkg loop, with callback.
        # The results get cached, so when yum does it again in the real
        # _downloadPackages function it's a negligible delay.
        localpkgs = [p for p in pkgs if os.path.exists(p.localPkg())]
        total = len(localpkgs)
        # XXX: multithreading?
        for num, p in enumerate(localpkgs, 1):
            local = p.localPkg()
            if hasattr(callback, "verify") and callable(callback.verify):
                callback.verify(num, total, local, None)
            ok = self.verifyPkg(local, p, False) # result will be cached by yum
        log.info("beginning package download...")
        updates = self._downloadPackages(callback)
        if set(updates) != set(pkgs):
            log.debug("differences between requested pkg set and downloaded:")
            for p in set(pkgs).difference(updates):
                log.debug("  -%s", p)
            for p in set(updates).difference(pkgs):
                log.debug("  +%s", p)
        # TODO check signatures of downloaded packages

    def clean_cache(self, keepfiles):
        log.info("checking for unneeded rpms in cache")
        # Find all the packages in the caches (not on media though)
        localpkgs = set(f for r in self.repos.listEnabled() if not r.mediaid
                          for f in listdir(r.pkgdir) if f.endswith(".rpm"))
        for f in localpkgs.difference(keepfiles):
            try:
                log.debug("removing %s", f)
                os.remove(f)
            except IOError as e:
                log.info("failed to remove %s", f)
        # TODO remove dirs that don't belong to any repo

    @property
    def instrepo(self):
        return self.repos.getRepo(self.instrepoid)

    @property
    def treeinfo(self):
        if self._treeinfo is None:
            mkdir_p(cachedir)
            outfile = os.path.join(cachedir, '.treeinfo')
            if self.cacheonly:
                log.debug("using cached .treeinfo %s", outfile)
                self._treeinfo = Treeinfo(outfile)
            else:
                log.debug("fetching .treeinfo from repo '%s'", self.instrepoid)
                if os.path.exists(outfile):
                    os.remove(outfile)
                fn = self.instrepo.grab.urlgrab('.treeinfo', outfile,
                                                reget=None)
                self._treeinfo = Treeinfo(fn)
                log.debug(".treeinfo saved at %s", fn)
            self._treeinfo.checkvalues()
        return self._treeinfo

    def download_boot_images(self, arch=None):
        # helper function to grab and checksum image files listed in .treeinfo
        def grab_and_check(imgarch, imgtype, outpath):
            relpath = self.treeinfo.get_image(imgarch, imgtype)
            log.debug("grabbing %s %s", imgarch, imgtype)
            log.info("downloading %s to %s", relpath, outpath)
            if self.treeinfo.checkfile(outpath, relpath):
                log.debug("file already exists and checksum OK")
                return outpath
            def checkfile(cb):
                log.debug("checking %s", relpath)
                if not self.treeinfo.checkfile(cb.filename, relpath):
                    log.info("checksum doesn't match - retrying")
                    raise yum.URLGrabError(-1)
            # TODO: use failure callback to log failure reason(s)
            return self.instrepo.grab.urlgrab(relpath, outpath,
                                              checkfunc=checkfile,
                                              reget=None,
                                              copy_local=True)

        # download the images
        try:
            if not arch:
                arch = self.treeinfo.get('general', 'arch')
            kernel = grab_and_check(arch, 'kernel', kernelpath)
            initrd = grab_and_check(arch, 'upgrade', initrdpath)
        except TreeinfoError as e:
            raise YumBaseError(_("invalid data in .treeinfo: %s") % str(e))
        except yum.URLGrabError as e:
            if e.errno >= 256:
                raise YumBaseError(_("couldn't get %s from repo") % key)
            else:
                raise YumBaseError(_("failed to download %s: %s") % (key, str(e)))

        return kernel, initrd

def link_pkgs(pkgs):
    '''link the named pkgs into packagedir, overwriting existing files.
       also removes any .rpm files in packagedir that aren't in pkgs.
       finally, write a list of packages to upgrade and a list of dirs
       to clean up after successful upgrade.'''

    log.info("linking required packages into packagedir")
    log.info("packagedir = %s", packagedir)
    if not os.path.isdir(packagedir):
        os.mkdir(packagedir, 0755)

    pkgbasenames = set()
    for pkg in pkgs:
        pkgpath = pkg.localPkg()
        if pkg.remote_url.startswith("file://"):
            pkgbasename = "media/%s" % pkg.relativepath
            pkgbasenames.add(pkgbasename)
            continue
        if not os.path.exists(pkgpath):
            log.warning("%s missing", pkgpath)
            continue
        pkgbasename = os.path.basename(pkgpath)
        pkgbasenames.add(pkgbasename)
        target = os.path.join(packagedir, pkgbasename)
        if os.path.exists(target) and os.lstat(pkgpath) == os.lstat(target):
            log.info("%s already in packagedir", pkgbasename)
            continue
        else:
            if os.path.isdir(target):
                log.info("deleting weirdo directory named %s", pkgbasename)
                rm_rf(target)
            elif os.path.exists(target):
                os.remove(target)
            try:
                os.link(pkgpath, target)
            except OSError as e:
                if e.errno == 18:
                    copy2(pkgpath, target)
                else:
                    raise

    # remove spurious / leftover RPMs
    for f in os.listdir(packagedir):
        if f.endswith(".rpm") and f not in pkgbasenames:
            os.remove(os.path.join(packagedir, f))

    # write packagelist
    with open(packagelist, 'w') as outf:
        outf.writelines(p+'\n' for p in pkgbasenames)

    # write cleanup data
    with Config(upgradeconf) as conf:
        # packagedir should probably be last, since it contains upgradeconf
        cleanupdirs = [cachedir, packagedir]
        conf.set("cleanup", "dirs", ';'.join(cleanupdirs))

def setup_upgradelink():
    log.info("setting up upgrade symlink: %s->%s", upgradelink, packagedir)
    try:
        os.remove(upgradelink)
    except OSError:
        pass
    os.symlink(packagedir, upgradelink)

def setup_media_mount(mnt):
    # make a "media" subdir where all the packages are
    mountpath = os.path.join(upgradelink, "media")
    log.info("setting up mount for %s at %s", mnt.dev, mountpath)
    mkdir_p(mountpath)
    # make a directory to place a unit
    mkdir_p(upgrade_target_wants)
    # make a modified mnt entry that puts it at mountpath
    mediamnt = mnt._replace(rawmnt=mountpath)
    # finally, write out a systemd unit to mount media there
    unit = write_systemd_unit(mediamnt, upgrade_target_wants)
    log.info("wrote %s", unit)

def setup_upgraderoot():
    if os.path.isdir(upgraderoot):
        log.info("upgrade root dir %s already exists", upgraderoot)
        return
    else:
        log.info("creating upgraderoot dir: %s", upgraderoot)
        os.makedirs(upgraderoot, 0755)

def prep_upgrade(pkgs):
    # put packages in packagedir (also writes packagelist)
    link_pkgs(pkgs)
    # make magic symlink
    setup_upgradelink()
    # make dir for upgraderoot
    setup_upgraderoot()

def modify_bootloader(kernel, initrd):
    log.info("adding new boot entry")

    args = ["upgrade", "systemd.unit=system-upgrade.target"]
    if not is_selinux_enabled():
        args.append("selinux=0")

    boot.add_entry(kernel, initrd, banner=_("System Upgrade"), kargs=args)

    # Save kernel/initrd info so we can clean it up later
    with Config(upgradeconf) as conf:
        conf.set("boot", "kernel", kernel)
        conf.set("boot", "initrd", initrd)
        conf.set("boot", "prevkernel", boot.get_default())

def prep_boot(kernel, initrd):
    # set up the boot args
    modify_bootloader(kernel, initrd)
    # and make it the default
    boot.set_default(kernel)

def remove_boot():
    '''find and remove our boot entry'''
    conf = Config(upgradeconf)
    kernel = conf.get("boot", "kernel")
    initrd = conf.get("boot", "initrd")
    prevkernel = conf.get("boot", "prevkernel")
    if kernel:
        rm_f(kernel)
        boot.remove_entry(kernel)
    if initrd:
        rm_f(initrd)
    if prevkernel:
        boot.set_default(prevkernel)

def remove_cache():
    '''remove our cache dirs'''
    conf = Config(upgradeconf)
    cleanup = conf.get("cleanup", "dirs") or ''
    cleanup = cleanup.split(';')
    cleanup += [cachedir, packagedir] # just to be sure
    for d in cleanup:
        log.info("removing %s", d)
        rm_rf(d)

def full_cleanup():
    '''remove all the files we create and undo any other changes'''
    remove_boot()
    remove_cache()
    log.info("removing symlink %s", upgradelink)
    rm_f(upgradelink)
    for d in (upgraderoot, upgrade_target_wants):
        log.info("removing %s", d)
        rm_rf(d)
