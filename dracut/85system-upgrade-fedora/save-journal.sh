#!/bin/sh

logpath=/sysroot/var/log/upgrade

simple_backup() {
    [ -e "$1.old" ] && rm -rf "$1.old"
    [ -e "$1" ] && mv "$1" "$1.old"
}

# save the journal
simple_backup $logpath.journal
cp -a /run/log/journal $logpath.journal

# write out the plain logfile for people who don't like the journal
simple_backup $logpath.log
journalctl -a -m > $logpath.log
