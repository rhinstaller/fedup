#!/usr/bin/python

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
