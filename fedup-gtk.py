#!/usr/bin/python
#
# fedup-gtk - GTK+ frontend for fedup, the Fedora Upgrader
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
#
# TODO:
# - Fix handling of KeyboardInterrupt and/or stuck UI on traceback
# - Use the same ArgumentParser as the CLI
# - Accept --instrepo

import os

from fedup import _

from gi.repository import GObject
GObject.threads_init()
from gi.repository import Gtk, GLib, Gio, Soup

from fedup.media import mounts, isblock, isloop

import logging, fedup.logutils
log = logging.getLogger("fedup.gtk")
fedup.logutils.consolelog(level=logging.INFO)

srcicon = dict(net="network-server-symbolic",
               dvd="media-optical-symbolic",
               usb="media-removable-symbolic",
               default="drive-removable-media-symbolic")

from collections import namedtuple
FedupSourceBase = namedtuple('FedupSource', 'id icon label available')

class FedupSource(FedupSourceBase):
    def __new__(cls, id, icon=None, label=None, available=True):
        if icon not in srcicon.values():
            icon = srcicon.get(icon) or srcicon.get('default')
        if label is None:
            label = id
        return FedupSourceBase.__new__(cls, id, icon, label, available)

# FIXME!!
def mirrorlist(ver):
    return "https://mirrors.fedoraproject.org/metalink?repo=fedora-install-%i&arch=x86_64" % ver

class FedupUI(object):
    def __init__(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(self.findUIFile("fedup.glade"))
        self.builder.connect_signals(self)
        self.window = self.builder.get_object("assistant")
        self.searchdialog = self.builder.get_object("searchdialog")
        self.soup = None
        self.did_srclist = False
        self.network = None

        self.srclist = self.builder.get_object("srcliststore")
        self.missingsrc = list(self.srclist_objs)

    @property
    def srclist_objs(self):
        for row in self.srclist:
            yield FedupSource._make(row)

    def findUIFile(self, filename):
        path = os.environ.get("UIPATH", ".:ui:/usr/share/fedup")
        for ui_dir in path.split(":"):
            uifile = os.path.normpath(os.path.join(ui_dir, filename))
            if os.path.isfile(uifile) and os.access(uifile, os.R_OK):
                return uifile
        raise IOError("Can't find UI file '%s'" % filename)

    def run(self):
        self.window.show_all()
        Gtk.main()

    def cancel(self, *args):
        Gtk.main_quit()

    def close(self, *args):
        Gtk.main_quit()

    def prepare(self, asst, *args):
        pageid = asst.get_current_page()
        page = asst.get_nth_page(asst.get_current_page())
        log.info("preparing page #%s", pageid)
        if pageid == 1 and not self.did_srclist:
            self.populate_srclist()

    def populate_srclist(self):
        log.info("showing search dialog")
        self.searchdialog.show_all()
        self.srclist.clear()
        self.to_check = list()

        version = 17 # FIXME: actually get version from host
        # FIXME: how do we determine what versions to look for?
        for v in (18,):
            self.checkuri(mirrorlist(v), version=v)

        for m in mounts():
            if isblock(m.dev) and m.mnt not in ("/", "/boot", "/boot/efi"):
                self.checkdev(m)

    def checkuri(self, uri, **kwargs):
        if not self.soup:
            self.soup = Soup.SessionAsync()
        msg = Soup.Message.new("GET", uri)
        self.to_check.append(uri)
        kwargs['uri'] = uri
        self.soup.queue_message(msg, self.checkuri_cb, kwargs)

    def checkuri_cb(self, sess, msg, kwargs):
        host = msg.props.uri.host
        uri = kwargs['uri']
        if self.network is None and msg.props.status_code == 200:
            self.network = True

        # FIXME: what about non-mirrorlist URIs?
        if "</url>" in msg.props.response_body.data:
            log.info("checkuri for %s succeeded", uri)
            self.srclist.append(FedupSource(uri, icon='net', label=host))
        else:
            log.info("checkuri for %s failed", uri)

        self.to_check.remove(uri)
        if not self.to_check:
            self.populate_srclist_finished()

    def checkdev(self, mnt):
        f = Gio.file_new_for_path(os.path.join(mnt.mnt, ".treeinfo"))
        self.to_check.append(mnt)
        # FIXME: attempt to read version from .treeinfo
        f.query_info_async(Gio.FILE_ATTRIBUTE_STANDARD_TYPE,
                           0, 0, None, self.checkdev_cb, mnt)

    def checkdev_cb(self, f, result, mnt):
        try:
            inf = f.query_info_finish(result)
            filetype = inf.get_file_type()
        except GLib.GError as e:
            filetype = None

        if filetype == Gio.FileType.REGULAR:
            log.info("%s is install media", mnt.dev)
            # FIXME: is this USB, a DVD, or a loop-mounted ISO?
            if isloop(mnt.dev):
                devtype = 'loop'
            else:
                devtype = 'usb'
            # FIXME: read version from file
            ver = '18'
            # add item to srclist
            self.srclist.insert(0, FedupSource(mnt.dev, icon=devtype))

        else:
            log.info("no .treeinfo in %s", mnt.mnt)

        self.to_check.remove(mnt)
        if not self.to_check:
            self.populate_srclist_finished()

    def populate_srclist_finished(self):
        log.info("finished populating srclist. rows: %i", len(self.srclist))
        for row in self.srclist:
            log.info(", ".join(str(i) for i in row[:]))

        # Add the "No installable DVD" items
        for missing in self.missingsrc:
            if not any(src.icon == missing.icon for src in self.srclist_objs):
                self.srclist.append(missing)

        # TODO: handle this in a property or with a signal or something
        if self.network:
            updates = self.builder.get_object("updatesbox")
            updates.props.sensitive = True

        self.searchdialog.hide()

        if any(FedupSource(*row).available for row in self.srclist):
            self.did_srclist = True
            combo = self.builder.get_object("sourcecombo")
            combo.set_active(0)
        else:
            log.info("no valid instrepos found")
            nosrc = self.builder.get_object("nosourcedialog")
            nosrc.show_all()

    def nosource_response(self, w, responseid):
        if responseid == 0:
            self.close()
        elif responseid == 1:
            w.hide()
            self.populate_srclist()

    def disable_delete(self, w, event):
        return True # ignore delete signal from Esc keypress

    def sourcecombo_changed(self, w, *args):
        src = FedupSource._make(self.srclist[w.get_active()])
        page = self.builder.get_object("sourcebox")
        self.window.set_page_complete(page, src.available)


if __name__ == '__main__':
    try:
        ui = FedupUI()
        ui.run()
    except IOError as e:
        print e
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(2)
