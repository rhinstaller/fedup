# fedup.sysinfo - get information about the host system

from dnf.rpm import detect_releasever

import rpm
import platform

def has_product_installed():
    """
    Return a list of rpm.hdr objects that provide system-release-product.
    In a boolean context, this tells us whether we have a product installed
    or not.
    """
    ts = rpm.ts()
    return list(ts.dbMatch('provides','system-release-product'))

def get_distro():
    dists = ('fedora',)
    distro, version, ident = platform.linux_distribution(supported_dists=dists)
    return distro, version
