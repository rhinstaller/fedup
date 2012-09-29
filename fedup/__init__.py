#!/usr/bin/python
# __init__.py for fedup - the Fedora Upgrade python package

import logging
log = logging.getLogger("fedup")
log.addHandler(logging.NullHandler())

import gettext
t = gettext.translation("fedup", "/usr/share/locale", fallback=True)
_ = t.lgettext

packagedir = '/var/cache/fedora-upgrade-packages'
