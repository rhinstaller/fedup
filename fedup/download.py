# fedup.download - yum-based download/depsolver for Fedora Upgrade

import os
import yum
import logging
from fedup.callback import BaseTsCallback
from yum.Errors import YumBaseError

enabled_plugins = ['blacklist', 'whiteout']
disabled_plugins = ['rpm-warm-cache', 'remove-with-leaves', 'presto',
                    'auto-update-debuginfo', 'refresh-packagekit']

cachedir="/var/tmp/fedora-upgrade"

log = logging.getLogger("fedup.yum")

def listdir(d):
    for f in os.listdir(d):
        yield os.path.join(d, f)

class FedupDownloader(yum.YumBase):
    '''Yum-based downloader class for fedup. Based roughly on AnacondaYum.'''
    def __init__(self, version=None, cachedir=cachedir):
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
        self.prerepoconf.cachedir = cachedir
        # TODO: locking to prevent multiple instances
        # TODO: override logging objects so we get yum logging

    def _getConfig(self):
        conf = yum.YumBase._getConfig(self)
        conf.disable_excludes = ['all']
        return conf

    def check_repos(self, callback=None, progressbar=None):
        '''Return a list of repos that had problems setting up.'''
        # FIXME invalidate cache if the version doesn't match previous version
        log.info("checking repos")
        disabled_repos = []

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
                disabled_repos.append(repo.id)
            else:
                log.info("repo %s seems OK" % repo.id)

        return disabled_repos

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
        for num, p in enumerate(localpkgs):
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
        self.clean_cache(p.localPkg() for p in updates)
        # TODO check signatures of downloaded packages

    def clean_cache(self, installpkgs):
        log.info("checking for unneeded rpms in cache")
        # Only clean stuff that's not on media
        repos = [r for r in self.repos.repos.values() if r.mediaid is None]
        # Find all the packages in the caches
        localpkgs = set(f for r in self.repos.listEnabled() if not r.mediaid
                          for f in listdir(r.pkgdir) if f.endswith(".rpm"))
        for f in localpkgs.difference(installpkgs):
            try:
                log.debug("removing %s", f)
                #os.remove(f)
            except IOError as e:
                log.info("failed to remove %s", f)
