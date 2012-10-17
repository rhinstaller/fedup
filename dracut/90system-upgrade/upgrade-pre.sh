#!/bin/sh

# upgrade-pre hook: before the upgrade, but after the disks are mounted
echo "starting upgrade-pre hook"

export DRACUT_SYSTEMD=1
if [ -f /dracut-state.sh ]; then
    . /dracut-state.sh 2>/dev/null
fi
type getarg >/dev/null 2>&1 || . /lib/dracut-lib.sh

source_conf /etc/conf.d

getarg 'rd.upgrade.break=pre' 'rd.break=upgrade-pre' && \
    emergency_shell -n upgrade-pre "Break before upgrade-pre hook"
source_hook upgrade-pre

exit 0
