#!/bin/sh

# upgrade-post hook: last-minute fixes, cleanups, etc.
echo "starting upgrade-post hook"

export DRACUT_SYSTEMD=1
if [ -f /dracut-state.sh ]; then
    . /dracut-state.sh 2>/dev/null
fi
type getarg >/dev/null 2>&1 || . /lib/dracut-lib.sh

source_conf /etc/conf.d

getarg 'rd.upgrade.break=post' 'rd.break=upgrade-post' && \
    emergency_shell -n upgrade-post "Break before upgrade-post hook"
source_hook upgrade-post

exit 0
