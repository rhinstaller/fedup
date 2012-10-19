#!/bin/sh

logpath=/sysroot/var/log/upgrade

# save the journal
cp -a /run/log/journal $logpath.journal

# write out the plain logfile for people who don't like the journal
journalctl -a -m > $logpath.log
