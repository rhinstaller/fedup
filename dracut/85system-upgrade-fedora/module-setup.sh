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
    # stuff we need for initial boot
    # ------------------------------
    # SELinux policy
    dracut_install /etc/selinux/config
    dracut_install /etc/selinux/*/contexts/files/*
    dracut_install /etc/selinux/*/policy/*
    # script to save initramfs at UPGRADEROOT
    inst_hook pre-pivot 99 "$moddir/keep-initramfs.sh"

    # stuff we use in upgrade hook(s)
    # -------------------------------
    # upgrader binary
    inst_binary $UPGRADEBIN

    # RPM hash/sig checks (via NSS) don't work without these
    inst_libdir_file "libfreebl*" "libsqlite*" "libsoftokn*"

    # RPM can't find the rpmdb without rpmconfig
    rpmconfig=$(find /etc/rpm /usr/lib/rpm -name "rpmrc" -o -name "macros*")
    dracut_install $rpmconfig

    # script to actually run the upgrader binary
    inst_hook upgrade 50 "$moddir/do-upgrade.sh"

    # workaround: systemd won't reboot without swapoff
    dracut_install swapoff

    # save the journal/logs after we're done
    inst_hook upgrade-post 99 "$moddir/save-journal.sh"
}
