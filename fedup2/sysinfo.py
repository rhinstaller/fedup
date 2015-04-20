# fedup.sysinfo - get information about the host system

from dnf.rpm import detect_releasever # pylint: disable=unused-import

import rpm
import platform

def has_product_installed():
    """
    Return a list of rpm.hdr objects that provide system-release-product.
    In a boolean context, this tells us whether we have a product installed
    or not.
    """
    ts = rpm.ts()
    # the rpm module doesn't introspect well, so.. pylint: disable=no-member
    return list(ts.dbMatch('provides','system-release-product'))

def get_distro():
    dists = ('fedora',)
    distro, version, _ = platform.linux_distribution(supported_dists=dists)
    return distro, version
