# fedup.sysinfo - get information about the host system

from dnf.rpm import detect_releasever

import rpm

def has_product_installed():
    """
    Return a list of rpm.hdr objects that provide system-release-product.
    In a boolean context, this tells us whether we have a product installed
    or not.
    """
    ts = rpm.ts()
    return list(ts.dbMatch('provides','system-release-product'))
