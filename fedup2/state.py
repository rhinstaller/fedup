# fedup.state - track upgrade state in a well-known place

statefile = '/var/lib/system-upgrade/upgrade.conf'

import os, json
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

    def summarize(self):
        # XXX STUB
        return "No upgrade in progress."

    def save_args(self, args, section="args", key="args_json"):
        '''Save an argparse.Namespace object into the config.'''
        nsdict = vars(args)               # get dict from Namespace
        jsonstr = json.dumps(nsdict)      # convert dict to json string
        self.set(section, key, jsonstr)   # write to config

    def get_args(self, section="args", key="args_json"):
        '''Load a Namespace object from the config.
           NOTE: in Python 2.x any string value will be a unicode object!'''
        jsonstr = self.get(section, key)  # read from config
        nsdict = json.loads(jsonstr)      # convert json string to dict
        return Namespace(**nsdict)        # put dict in Namespace

    def remove_args(self, section="args", key="args_json"):
        return self.remove(section, key)

    def __str__(self):
        return self.summarize()

def getstate():
    return State()
