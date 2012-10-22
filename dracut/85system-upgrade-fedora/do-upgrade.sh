#!/bin/bash
# actually perform the upgrade

upgradepath=/usr/lib/systemd

do_upgrade() {
    local args=""
    getargbool 0 rd.upgrade.test && args="$args --testing"
    getargbool 0 rd.upgrade.verbose && args="$args --verbose"
    getargbool 0 rd.upgrade.debug && args="$args --debug"

    # enable plymouth output unless specifically disabled
    getargbool 1 plymouth.enable && args="$args --plymouth"

    # and off we go...
    $upgradepath/fedora-system-upgrade --root=/sysroot $args \
        >> /sysroot/var/log/upgrade.out
    # FIXME: we're only writing to that log file because our output isn't going
    # to journald - see https://bugzilla.redhat.com/show_bug.cgi?id=869061
}

do_upgrade
