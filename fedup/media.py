# fedup.media - check for installable media

import os, stat
from collections import namedtuple
from os.path import exists, join

FstabEntry = namedtuple('FstabEntry', 'dev mntpoint type opts freq passno')

def mounts(fstab="/proc/mounts"):
    for line in open(fstab):
        yield FstabEntry(*line.split())

def ismedia(mountpoint):
    return exists(join(mountpoint, ".buildstamp"))

def isblock(dev):
    return exists(dev) and stat.S_ISBLK(os.stat(dev).st_mode)

def find():
    return [m for m in mounts() if isblock(m.dev) and ismedia(m.mntpoint)]
