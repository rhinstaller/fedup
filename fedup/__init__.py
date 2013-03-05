# __init__.py for fedup - the Fedora Upgrade python package
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

import logging
log = logging.getLogger("fedup")
log.addHandler(logging.NullHandler())

import gettext
t = gettext.translation("fedup", "/usr/share/locale", fallback=True)
_ = t.lgettext

kernel_id = 'fedup'
# NOTE: new-kernel-pkg requires this kernel name/path
kernelpath = '/boot/vmlinuz-%s' % kernel_id
initrdpath = '/boot/initramfs-%s.img' % kernel_id

cachedir = '/var/tmp/fedora-upgrade'
packagedir = '/var/lib/fedora-upgrade'
packagelist = packagedir + '/package.list'
upgradeconf = packagedir + '/upgrade.conf'
upgradelink = '/system-upgrade'
upgraderoot = '/system-upgrade-root'

mirrormanager = 'https://mirrors.fedoraproject.org/metalink'

update_img_dir = '/etc/fedup/update.img.d'
