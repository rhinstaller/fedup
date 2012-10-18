#!/bin/sh

echo "UPGRADEROOT=$UPGRADEROOT" > /run/initramfs/upgrade.conf

plymouth --change-mode updates
