#!/usr/bin/env python
# prototype downloader component for fedup 2.0

import os
import sys
import argparse

import dnf
import dnf.cli
import dnf.exceptions

default_instrepo = '@https://mirrors.fedoraproject.org/metalink?' \
                   'repo=fedora-install-$releasever&arch=$basearch'

def hrsize(numbytes):
    # dumb placeholder: just return size in MiB
    return "%dMiB" % ((numbytes>>20)+1)

def parse_args():
    # TODO implement this for real
    args = argparse.Namespace()
    args.pkgdir = "/var/lib/system-upgrade"
    args.version = "rawhide"
    args.cachedir = None
    args.instrepo = default_instrepo
    args.quicktest = True
    args.ipython = True
    return args

def write_packagelist(pkglist, pkgdir):
    '''
    Write packages.list into pkgdir, which contains relative paths to
    all the packages named in pkglist.
    These are the packages that will be installed when we run the upgrade tool.
    '''
    with open(os.path.join(pkgdir,"packages.list"), "w") as f:
        for p in pkglist:
            f.write(os.path.relpath(p.localPkg(), pkgdir) + '\n')

def setup_base(args):
    # create dnf object
    base = dnf.cli.cli.BaseCli()

    # prepare progress callbacks
    repobar, base.ds_callback = base.output.setup_progress_callbacks()

    # set releasever before we do anything else
    base.conf.substitutions['releasever'] = args.version
    # set cachedir before we start messing with repos
    if args.cachedir is not None:
        base.conf.cachedir = args.cachedir
    # ..add CACHEDIR_SUFFIX (note: these are the same directory if you're root)
    base.conf.cachedir, sys_cachedir = dnf.cli.cli.cachedir_fit(base.conf)

    # read repo config
    print("reading repo config")
    base.read_all_repos()

    # also create instrepo and add it to the repo config
    instrepo = dnf.repo.Repo('instrepo', base.conf.cachedir)
    instrepo.substitutions.update(base.conf.substitutions)

    def subst(rawstr):
        return dnf.conf.parser.substitute(rawstr, base.conf.substitutions)

    # NOTE: the progressbar will trace back if you don't set name
    instrepo.name = subst("Install Image Repo - $releasever - $basearch")
    if args.instrepo.startswith('@'):
        instrepo.metalink = subst(args.instrepo[1:])
    else:
        instrepo.baseurl = [subst(args.instrepo)]
    base.repos.add(instrepo)

    # change pkgdir to our target dir
    base.repos.all().pkgdir = args.pkgdir

    # add progress callback
    base.repos.all().set_progress_bar(repobar)

    # TODO: subclass dnf.cli.output.CliKeyImport to handle our key behavior
    #key_import = FedupCliKeyImport()
    #base.repos.all().set_key_import(key_import)

    return base

def find_upgrade_packages(base, args):
    print("setting up repos")

    # read rpmdb to find installed packages, get metadata for new pkgs
    # TODO handle repos that fail to configure
    base.fill_sack(load_system_repo=True, load_available_repos=True)

    print("finding upgrades")

    # find all available upgrades
    # TODO: distro-sync mode (allow downgrades)
    rv = base.upgrade_all()
    ok = base.resolve()
    pkglist = base.transaction.install_set

    print("found %i upgrades (rv=%i, ok=%s)" % (len(pkglist), rv, ok))
    dlsize = sum(p.size for p in pkglist)
    print("download size: %s" % hrsize(dlsize))

    # debugging: "quicktest" means just do the first 10 packages
    if args.quicktest:
        pkglist = sorted(pkglist)[:10]

    return pkglist

def download_packages(base, pkglist):
    print("downloading upgrade packages")
    dlprogress = dnf.cli.progress.MultiFileProgressMeter(fo=sys.stdout)
    base.download_packages(pkglist, progress=dlprogress)

def get_handle(repo):
    h = repo.get_handle()
    h.destdir = repo.cachedir
    if os.access(h.metalink_path, os.R_OK):
        h.mirrorlist = h.metalink_path
    elif os.access(h.mirrorlist_path, os.R_OK):
        h.mirrorlist = h.mirrorlist_path
    h.fetchmirrors = True
    h.yumdlist = []
    h.perform()
    return h

def download_file(relpath, handle=None, local_name=None):
    if local_name is None:
        local_name = os.path.basename(relpath)
    fullpath = os.path.join(handle.destdir, local_name)
    with open(fullpath, "w+") as f:
        librepo.download_url(relpath, f.fileno(), handle)
    return fullpath

if __name__ == '__main__':
    # TODO: logging setup
    try:
        args = parse_args()
        base = setup_base(args)
        pkglist = find_upgrade_packages(base, args)
        download_packages(base, pkglist)
        write_packagelist(pkglist, args.pkgdir)
    # TODO: real exception handling obvy
    except dnf.exceptions.DownloadError as e:
        print("downloading packages failed, bummer :<")
    except dnf.exceptions.DepsolveError as e:
        print("depsolving failed, another bummer")
    except KeyboardInterrupt:
        pass

    if args.ipython:
        h = get_handle(base.repos['instrepo'])
        from IPython import embed
        embed()
