system-upgrade
==============
Will Woods <wwoods@redhat.com>
// vim: syn=asciidoc tw=78:

This module adds targets suitable for system upgrades.

The upgrade workflow is something like this:

. Using the *new* distro version, create an initramfs with `system-upgrade`.
    * Any other module starting with `system-upgrade-` will be included, e.g.:
      * distro-specific upgrade tool
      * distro-specific migration scripts
      * package-specific migration scripts
. Boot the *new* kernel/initramfs on the system to be upgraded.
    * `UPGRADEROOT` will be written to `/run/initramfs/upgrade.conf`
    * distro-specific modules may want to save initramfs to `$UPGRADEROOT` here
    * distro-specific filesystem migration should use the `pre-mount` hook
. The system mounts its local disks.
. The system prepares `$UPGRADEROOT`
    * The root directory gets recursive-bind-mounted to `$UPGRADEROOT/sysroot`
    * `$UPGRADEROOT/lib/systemd/default.target` is linked to `upgrade.target`
    * distros might unpack the `upgrade.img` to `$UPGRADEROOT` here instead
. The system does `switch-root` back into the initramfs
    * This time we're going to `upgrade.target` instead
. The `upgrade-pre` service/hook runs
    * After=`upgrade.target`
. The `upgrade` service/hook runs
    * distro-specific upgrade tools should run here
. The `upgrade-post` service/hook runs
. The system is rebooted.

It's probably a good idea to take a filesystem snapshot in `pre-mount` or `pre-pivot`. If anything goes wrong, restore the snapshot in `upgrade-post`.
