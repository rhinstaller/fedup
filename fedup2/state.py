# fedup.state - track upgrade state in a well-known place

statefile = '/var/lib/system-upgrade/upgrade.conf'

import os
from .conf import Config
from .i18n import _

class State(Config):
    '''
    This holds the persistent bits of upgrade state (i.e. the stuff that stays
    between invocations of the fedup command), and some methods for telling the
    user about where we're at.
    '''
    def __init__(self):
        Config.__init__(self, statefile)

    @property
    def summary(self):
        return _("No upgrade in progress.")

def get_upgrade_state():
    return State()
