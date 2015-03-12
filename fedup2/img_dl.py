#!/usr/bin/env python
# prototype image downloader component for fedup 2.0

import os
import sys
import argparse

import dnf
import dnf.cli
import dnf.exceptions
# we need this for manually doing substitutions 'til the API is fixed
import dnf.conf.parser

import librepo

import treeinfo

default_instrepo = '@https://mirrors.fedoraproject.org/metalink?' \
                   'repo=fedora-install-$releasever&arch=$basearch'

def parse_args():
    # TODO implement this for real
    args = argparse.Namespace()
    args.nogpgcheck = True
    args.pkgdir = "/var/lib/system-upgrade"
    args.version = "21"
    args.cachedir = None
    args.instrepo = default_instrepo
    args.quicktest = True
    args.ipython = False
    return args

def setup_repo(args):
    # create dnf object
    dl = dnf.cli.cli.BaseCli() # XXX no, will, this is not public API

    # set releasever and cachedir before we read the repo config
    dl.conf.substitutions['releasever'] = args.version
    if args.cachedir is not None:
        dl.conf.cachedir = args.cachedir
    # Add CACHEDIR_SUFFIX (note: these are the same directory if you're root)
    dl.conf.cachedir, sys_cachedir = dnf.cli.cli.cachedir_fit(dl.conf)

    # prepare progress callbacks
    repobar, dl.ds_callback = dl.output.setup_progress_callbacks()
    dlprogress = dnf.cli.progress.MultiFileProgressMeter(fo=sys.stdout)

    # currently substitution only happens when we parse the file, but we're not
    # parsing a file, so.... (see dnf.conf.parser.ConfigPreProcessor)
    def subst(rawstr):
        return dnf.conf.parser.substitute(rawstr, dl.conf.substitutions)

    # create instrepo
    instrepo = dnf.repo.Repo('instrepo', dl.conf.cachedir)
    instrepo.substitutions = dl.conf.substitutions
    # NOTE: the progressbar will trace back if you don't set name
    instrepo.name = subst("Install Image Repo - $releasever - $basearch")
    if args.instrepo.startswith('@'):
        instrepo.mirrorlist = subst(args.instrepo[1:])
    else:
        instrepo.baseurl = [subst(args.instrepo)]
    instrepo.pkgdir = subst(args.pkgdir)
    # TODO: gpgkey
    instrepo.set_progress_bar(repobar)

    return instrepo

# FIXME need progress meter!
def download_file(relpath, handle=None, local_name=None):
    if local_name is None:
        local_name = os.path.basename(relpath)
    fullpath = os.path.join(handle.destdir, local_name)
    with open(fullpath, "w+") as f:
        librepo.download_url(relpath, f.fileno(), handle)
    # XXX blorp logging
    print("saved %s as %s" % (relpath, fullpath))
    return fullpath

def get_images(repo, args):
    # grab the librepo handle
    h = repo.get_handle()
    # need to set destdir (get_handle() docs mention it's unset)
    h.destdir = repo.cachedir
    # set this to make it set up mirror stuff
    h.fetchmirrors = True
    # don't download extra metadata though
    h.yumdlist = []
    # set up mirrors etc.
    h.perform()
    # ensure destdir exists
    dnf.util.ensure_dir(h.destdir)

    # grab .treeinfo
    if args.nogpgcheck:
        treeinfo_file = download_file(".treeinfo", h)
    else:
        treeinfo_signed = download_file(".treeinfo.signed", h)
        treeinfo_file = treeinfo_signed[:-7] # drop '.signed'
        # FIXME verify .treeinfo.signed -> .treeinfo cleartext

    # parse .treeinfo
    with open(treeinfo_file, "r") as t:
        ti = treeinfo.Treeinfo(t, topdir=h.destdir)

    section = "images-" + repo.substitutions['basearch']

    # grab kernel
    kernel = download_file(ti.get(section, "kernel"), h)
    # FIXME: try next mirror if checksum fails
    if not ti.checkfile(kernel, ti.get(section, "kernel")):
        print("checksum failure blahhhh")
        raise SystemExit(1)

    # grab upgrade.img
    initrd = download_file(ti.get(section, "upgrade"), h)
    # FIXME: try next mirror if checksum fails
    if not ti.checkfile(initrd, ti.get(section, "upgrade")):
        print("checksum failure blahhhh")
        raise SystemExit(1)

def main():
    args = parse_args()
    repo = setup_repo(args)

    # If we're debugging, start ipython
    if args.ipython:
        from IPython import embed
        embed()
        return

    kernel, initrd = get_images(repo, args)

    # TODO: need to write state somewhere so `reboot` can find kernel/initrd

if __name__ == '__main__':
    try:
        main()
    except dnf.exceptions.DownloadError as e:
        print("downloading packages failed, bummer :<")
    except KeyboardInterrupt:
        pass
