import ConfigParser
import hashlib
import time
import logging

log = logging.getLogger('fedup.treeinfo')

def hexdigest(filename, algo):
    hasher = hashlib.new(algo)
    with open(filename, 'rb') as fobj:
        while True:
            data = fobj.read(8192)
            if not data:
                break
            hasher.update(data)
    return hasher.hexdigest()

class Treeinfo(ConfigParser.RawConfigParser):
    '''
    A subclass of RawConfigParser with some extra bits for handling .treeinfo
    files, such as are written by pungi and friends.
    '''
    def __init__(self, data=None, fp=None):
        ConfigParser.RawConfigParser.__init__(self, allow_no_value=True)
        if data:
            self.read(data)
        if fp:
            self.readfp(fp)

    def get_image(self, arch, imgtype):
        return self.get('images-%s' % arch, imgtype)

    def checkvalues(self):
        if not self.has_section('general'):
            raise ConfigParser.ParsingError("[general] section missing")
        items = dict(self.items('general'))
        req_fields = ('name', 'version', 'arch')
        missing = [f for f in req_fields if not items.get(f, None)]
        if missing:
            raise ConfigParser.ParsingError(
                     "[general] missing value for %s" % ', '.join(missing))

    def checkfile(self, filename, relpath):
        val = self.get('checksums', relpath)
        algo, checksum = val.split(':',1)
        return (checksum == hexdigest(filename, algo))

TreeinfoError = ConfigParser.Error
