# textoutput - text output routines for fedora-upgrade
# vim: set fileencoding=utf8:

import os, sys, time

import rpm
sys.path.insert(0, '/usr/share/yum-cli')
from output import YumTextMeter, CacheProgressCallback

from fedup.callback import *

# TODO i18n
_ = lambda x: x

import logging
log = logging.getLogger("fedup.cli")

import fcntl, struct, termios
def termwidth(fd=1):
    try:
        buf = 'abcdefgh'
        buf = fcntl.ioctl(fd, termios.TIOCGWINSZ, buf)
        width = struct.unpack('hhhh', buf)[1]
    except IOError:
        width = 0
    return width

class SimpleProgress(object):
    def __init__(self, maxval, prefix="", barstyle='[=]', width=termwidth,
                 update_interval=0.3, width_interval=1.0, tty=sys.stdout):
        self.maxval = maxval
        self.curval = 0
        self.formatstr = "{0.prefix} {0.percent:2}% {0.bar}"
        self.barstyle = barstyle
        self.prefix = prefix
        # update screen at a certain interval
        self.tty = tty
        self.update_interval = update_interval
        self.screenupdate = 0
        # check terminal width every so often and adjust output
        # TODO: dumb. use SIGWINCH instead.
        self.width_interval = width_interval
        self.widthupdate = 0
        if callable(width):
            self.getwidth = width
        else:
            self.getwidth = lambda: width

    @property
    def width(self):
        now = time.time()
        if now - self.widthupdate > self.width_interval:
            self.widthupdate = now
            self._width = self.getwidth()
        return self._width

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

    def update(self, newval):
        now = time.time()
        self.curval = min(newval, self.maxval)
        if now - self.screenupdate > self.update_interval:
            self.screenupdate = now
            self.tty.write("\r%s" % self)
            self.tty.flush()

    def finish(self):
        self.update(self.maxval)
        self.tty.write("\r\n")

class RepoProgress(YumTextMeter):
    pass

class RepoCallback(object):
    def __init__(self, prefix="repo", tty=sys.stderr):
        self._pb = SimpleProgress(10, prefix=prefix, tty=tty)
    def progressbar(self, current, total, name=None):
        if name:
            self._pb.prefix = "repo (%s)" % name
        self._pb.maxval = total
        self._pb.update(current)
    def __del__(self):
        self._pb.finish()

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
        if amount+1 >= total:
            self.bar.finish()

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
