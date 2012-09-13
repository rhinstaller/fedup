#!/bin/bash
# ex: ts=8 sw=4 sts=4 et filetype=sh

check() {
    return 255
}

# pull in any other "system-upgrade-*" modules that exist
depends() {
    local mod_dir mod
    for mod_dir in $moddir/../[0-9][0-9]*; do
        [ -d $mod_dir ] || continue
        mod=${mod_dir##*/[0-9][0-9]}
        strstr "$mod" "system-upgrade-" && echo $mod
    done
    return 0
}

# we don't do anything here - other modules do any real work
install() {
    return 0
}

