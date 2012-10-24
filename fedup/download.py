# fedup.download - yum-based download/depsolver for Fedora Upgrade

import os
import yum
import logging
from fedup.callback import BaseTsCallback
from fedup.grubby import Grubby
from yum.Errors import YumBaseError

enabled_plugins = ['blacklist', 'whiteout']
disabled_plugins = ['rpm-warm-cache', 'remove-with-leaves', 'presto',
                    'auto-update-debuginfo', 'refresh-packagekit']

cachedir="/var/tmp/fedora-upgrade"

from fedup import packagedir, packagelist, upgradelink, upgraderoot

log = logging.getLogger("fedup.yum") # XXX kind of misleading?

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

    def setup_repos(self, callback=None, progressbar=None, repos=[]):
        '''Return a list of repos that had problems setting up.'''
        # FIXME invalidate cache if the version doesn't match previous version
        log.info("checking repos")
        disabled_repos = []

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
        # Only clean stuff that's not on media
        repos = [r for r in self.repos.repos.values() if r.mediaid is None]
        # Find all the packages in the caches
        localpkgs = set(f for r in self.repos.listEnabled() if not r.mediaid
                          for f in listdir(r.pkgdir) if f.endswith(".rpm"))
        for f in localpkgs.difference(keepfiles):
            try:
                log.debug("removing %s", f)
                os.remove(f)
            except IOError as e:
                log.info("failed to remove %s", f)
        # TODO remove dirs that don't belong to any repo

def link_pkgs(pkgs):
    '''link the named pkgs into packagedir, overwriting existing files.
       also removes any .rpm files in packagedir that aren't in pkgs.'''

    log.info("linking required packages into packagedir")
    log.info("packagedir = %s", packagedir)
    if not os.path.isdir(packagedir):
        os.mkdir(packagedir, 0755)

    pkgbasenames = set()
    for pkgpath in pkgs:
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
                shutil.rmtree(target)
            elif os.path.exists(target):
                os.remove(target)
            os.link(pkgpath, target)

    # remove spurious / leftover RPMs
    for f in os.listdir(packagedir):
        if f.endswith(".rpm") and f not in pkgbasenames:
            os.remove(os.path.join(packagedir, f))

    # write packagelist
    with open(packagelist, 'w') as outf:
        outf.writelines(p+'\n' for p in pkgbasenames)

def setup_upgradelink():
    log.info("setting up upgrade symlink: %s->%s", upgradelink, packagedir)
    try:
        os.remove(upgradelink)
    except OSError:
        pass
    os.symlink(packagedir, upgradelink)

def setup_upgraderoot():
    if os.path.isdir(upgraderoot):
        log.info("upgrade root dir %s already exists", upgraderoot)
        return
    else:
        log.info("creating upgraderoot dir: %s", upgraderoot)
        os.makedirs(upgraderoot, 0755)

def modify_bootloader():
    log.info("reading bootloader config")
    bootloader = Grubby()
    default = bootloader.default_entry()
    log.info("default boot entry: \"%s\", %s", default.title, default.root)

    # avoid duplicate boot entries
    for e in bootloader.get_entries():
        if e.kernel == "/boot/upgrade/vmlinuz":
            log.info("removing existing boot entry for %s", e.kernel)
            bootloader.remove_entry(e.index)

    log.info("adding new boot entry")
    bootloader.add_entry(kernel="/boot/upgrade/vmlinuz",
                         initrd="/boot/upgrade/upgrade.img",
                         title=_("System Upgrade"),
                         args="systemd.unit=system-upgrade.target")
    # FIXME: systemd.unit isn't necessary if we're running F18 or later -
    #        check the system version to see if we actually need that.

    # FIXME: use grub2-reboot to change to new bootloader config

def prep_upgrade(pkgs, bootloader=True):
    # put packages in packagedir (also writes packagelist)
    link_pkgs(pkgs)
    # make magic symlink
    setup_upgradelink()
    # make dir for upgraderoot
    setup_upgraderoot()
    # mess with the bootloader, if requested
    if bootloader:
        modify_bootloader()
