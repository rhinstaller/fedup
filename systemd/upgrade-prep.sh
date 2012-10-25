#!/bin/bash
# upgrade-prep.sh - set up upgrade dir for upgrading
# TODO: this should be done by something like 'systemctl pivot-root'

die() { echo "$@"; exit 1; }

. /run/initramfs/upgrade.conf || die "can't find /run/initramfs/upgrade.conf"
[ -n "$UPGRADEROOT" ] || die "UPGRADEROOT is not set"
[ -d "$UPGRADEROOT" ] || die "$UPGRADEROOT does not exist"

echo "binding / into $UPGRADEROOT"
# bind-mount / into the upgrade chroot so we can upgrade it
mount --rbind / $UPGRADEROOT/sysroot || die "couldn't bind / into upgrade dir"

# XXX: we can drop this once there's a way to pass args to new init
echo "switching upgraderoot default target to upgrade.target"
# switch the upgrade chroot target to upgrade.target
unitdir=$UPGRADEROOT/lib/systemd/system
ln -sf upgrade.target $unitdir/default.target

echo "upgrade prep complete"
