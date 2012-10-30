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

import os

from fedup import _

from gi.repository import GObject
GObject.threads_init()
from gi.repository import Gtk, GLib

class FedupUI(object):
    def __init__(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(self.findUIFile("fedup.glade"))
        self.builder.connect_signals(self)
        self.window = self.builder.get_object("assistant")

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
        print "close!"
        Gtk.main_quit()

if __name__ == '__main__':
    try:
        ui = FedupUI()
        ui.run()
    except IOError as e:
        print e
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(2)
