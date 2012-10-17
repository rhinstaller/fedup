#!/bin/bash
# ex: ts=8 sw=4 sts=4 et filetype=sh

upgrade_hooks="upgrade-pre upgrade upgrade-post"

check() {
    hookdirs+="$upgrade_hooks "
    return 255
}

depends() {
    echo "systemd"
    # pull in any other "system-upgrade-*" modules that exist
    local mod_dir mod
    for mod_dir in $dracutbasedir/modules.d/[0-9][0-9]*; do
        [ -d $mod_dir ] || continue
        mod=${mod_dir##*/[0-9][0-9]}
        strstr "$mod" "system-upgrade-" && echo $mod
    done
    return 0
}

install() {
    # Set UPGRADEROOT
    inst_hook cmdline 01 "$moddir/upgrade-init.sh"
    # Save UPGRADEROOT for running system
    inst_hook pre-pivot 99 "$moddir/upgrade-pre-pivot.sh"

    # Set up systemd target and units
    unitdir="$systemdsystemunitdir"
    upgrade_wantsdir="${initdir}${unitdir}/upgrade.target.wants"

    inst_simple "$moddir/upgrade.target" "$unitdir/upgrade.target"

    mkdir -p "$upgrade_wantsdir"
    for s in $upgrade_hooks; do
        inst_simple "$moddir/$s.service" "$unitdir/$s.service"
        inst_script "$moddir/$s.sh"      "/bin/$s"
        ln -sf "../$s.service" $upgrade_wantsdir
    done

}

