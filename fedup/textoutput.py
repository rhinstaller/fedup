# textoutput - text output routines
# vim: set fileencoding=UTF-8:
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

import os, sys, time

import rpm
sys.path.insert(0, '/usr/share/yum-cli')
from output import YumTextMeter, YumTextMultiFileMeter, CacheProgressCallback
from output import YumOutput
from urlgrabber.progress import terminal_width_cached

from .callback import *

from . import _

import logging
log = logging.getLogger(__package__+".cli")


class SimpleProgress(object):
    def __init__(self, maxval, prefix="", barstyle='[=]', update_interval=0.3,
                 tty=sys.stdout):
        self.maxval = maxval
        self.curval = 0
        self.formatstr = "{0.prefix} {0.percent:2}% {0.bar}"
        self.barstyle = barstyle
        self.prefix = prefix
        # update screen at a certain interval
        self.tty = tty
        self.update_interval = update_interval
        self.screenupdate = 0

    @property
    def width(self):
        return terminal_width_cached(self.tty.fileno())

    @property
    def percent(self):
        return int(100*self.curval / float(self.maxval))

    bar_fmt = "{l_br}{barchar:<{width}}{r_br}"
    @property
    def bar(self):
        otherstuff = self.formatstr.replace("{0.bar}","")
        barwidth = self.width - len(otherstuff.format(self)) - 2 # 2 brackets
        fillpart = barwidth * self.curval / self.maxval
        return self.bar_fmt.format(l_br=self.barstyle[0],
                                   barchar=self.barstyle[1] * fillpart,
                                   r_br=self.barstyle[2],
                                   width=barwidth)

    def __str__(self):
        return self.formatstr.format(self)

    def update(self, newval, forceupdate=False):
        now = time.time()
        self.curval = min(newval, self.maxval)
        if forceupdate or (now - self.screenupdate > self.update_interval):
            self.screenupdate = now
            self.tty.write("\r%s" % self)
            self.tty.flush()

    def finish(self):
        self.update(self.maxval, forceupdate=True)
        self.tty.write("\n")

class RepoProgress(YumTextMeter):
    def start(self, *args, **kwargs):
        YumTextMeter.start(self, *args, **kwargs)
        log.info("download %s" % self.text)

class RepoMultiProgress(YumTextMultiFileMeter):
    def start_meter(self, meter, now):
        YumTextMultiFileMeter.start_meter(self, meter, now)
        log.info("download %s" % meter.text)

class RepoCallback(object):
    def __init__(self, prefix="repodata", tty=sys.stderr):
        self._pb = SimpleProgress(10, prefix=prefix, tty=tty)
    def progressbar(self, current, total, name=None):
        if name:
            self._pb.prefix = "repodata (%s)" % name
        self._pb.maxval = total
        self._pb.update(current)

class DepsolveCallback(DepsolveCallbackBase):
    def __init__(self, yumobj=None, tty=sys.stderr):
        DepsolveCallbackBase.__init__(self, yumobj)
        self.progressbar = None
        if yumobj and tty:
            self.progressbar = SimpleProgress(self.installed_packages, tty=tty,
                                              prefix=_("finding updates"))

    def pkgAdded(self, tup, mode):
        DepsolveCallbackBase.pkgAdded(self, tup, mode)
        if self.progressbar and mode == "ud":
            self.progressbar.update(self.mode_counter['ud'])

    def end(self):
        DepsolveCallbackBase.end(self)
        if self.progressbar:
            self.progressbar.finish()
            self.progressbar = None

class DownloadCallback(DownloadCallbackBase):
    def __init__(self, tty=sys.stderr):
        DownloadCallbackBase.__init__(self)
        self.bar = SimpleProgress(10, tty=tty, prefix=_("verify local files"))

    def verify(self, amount, total, filename, data):
        DownloadCallbackBase.verify(self, amount, total, filename, data)
        if self.bar.maxval != total:
            self.bar.maxval = total
        self.bar.update(amount)
        if amount == total:
            self.bar.finish()

    def userconfirm(self):
        return YumOutput().userconfirm()

class TransactionCallback(RPMTsCallback):
    def __init__(self, numpkgs=0, tty=sys.stderr, prefix="rpm"):
        RPMTsCallback.__init__(self)
        self.numpkgs = numpkgs
        self.donepkgs = 0
        self.progressbar = SimpleProgress(10, prefix="rpm transaction", tty=tty)
    def trans_start(self, amount, total, key, data):
        if amount != 6:
            log.warn("weird: trans_start() with amount != 6")
        self.progressbar.maxval = total
    def trans_progress(self, amount, total, key, data):
        self.progressbar.update(amount)
    def trans_stop(self, amount, total, key, data):
        self.progressbar.finish()

    def inst_open_file(self, amount, total, key, data):
        log.info("installing %s (%u/%u)", os.path.basename(key),
                                          self.donepkgs+1, self.numpkgs)
        if self.donepkgs == 0:
            self.progressbar.prefix = "rpm install"
            self.progressbar.maxval = self.numpkgs
        self.progressbar.update(self.donepkgs)
        return RPMTsCallback.inst_open_file(self, amount, total, key, data)

    def inst_close_file(self, amount, total, key, data):
        RPMTsCallback.inst_close_file(self, amount, total, key, data)
        self.donepkgs += 1

    def uninst_start(self, amount, total, key, data):
        log.info("cleaning %s", key)

    def __del__(self):
        if self.progressbar:
            self.progressbar.finish()
