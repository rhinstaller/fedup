#!/bin/sh

die() { warn "$*"; exit 1; }

upgradedir="$NEWROOT/$UPGRADEROOT"

[ -n "$UPGRADEROOT" ] || die "UPGRADEROOT is unset, can't save initramfs"
[ -d "$upgradedir" ] || die "'$upgradedir' doesn't exist"

mount -t tmpfs -o mode=755 tmpfs "$upgradedir" \
    || die "Can't mount tmpfs for $upgradedir"

cp -ax / "$upgradedir" || die "failed to save initramfs to $upgradedir"
