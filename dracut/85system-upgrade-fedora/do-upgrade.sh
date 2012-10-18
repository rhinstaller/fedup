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
    $upgradepath/fedora-system-upgrade --root=/sysroot $args
}

do_upgrade
