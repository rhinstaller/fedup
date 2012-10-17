#!/bin/sh

# upgrade hook: distro-specific modules will add their upgrade tasks here
echo "starting upgrade hook"

export DRACUT_SYSTEMD=1
if [ -f /dracut-state.sh ]; then
    . /dracut-state.sh 2>/dev/null
fi
type getarg >/dev/null 2>&1 || . /lib/dracut-lib.sh

source_conf /etc/conf.d

getarg 'rd.upgrade.break=upgrade' 'rd.break=upgrade' && \
    emergency_shell -n upgrade "Break before upgrade"

source_hook upgrade

exit 0
