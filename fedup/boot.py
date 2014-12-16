# boot - generic bootloader config modification code
#
# Copyright (C) 2014 Red Hat Inc.
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

# Poke around the system to decide which implementation to use.
from os.path import exists
if exists("/sbin/new-kernel-pkg"):
    from .grubby import *
# Other implementations would go here, e.g.:
#elif exists("/bin/kernel-install"):
#    from .kernelinstall import *
else:
    raise ImportError, "Can't find new-kernel-pkg or kernel-install"
