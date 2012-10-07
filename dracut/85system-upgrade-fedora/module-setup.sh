#!/bin/bash

UPGRADEBIN=/usr/lib/systemd/fedora-system-upgrade

check() {
    [ -x $UPGRADEBIN ] || return 1
    return 255
}

depends() {
    echo plymouth
}

install() {
    inst_binary $UPGRADEBIN
    inst_libdir_file "libfreebl*" "libsqlite*" "libsoftokn*"
    rpmconfig=$(find /etc/rpm /usr/lib/rpm -name "rpmrc" -o -name "macros*")
    dracut_install $rpmconfig
}
