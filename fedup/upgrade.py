# fedup.upgrade - actually run the upgrade.
# For the sake of simplicity, we don't bother with yum here.

import rpm
from rpm._rpm import ts as TransactionSetCore

import logging
log = logging.getLogger('fedup.upgrade')

_ = lambda x: x # FIXME i18n

class TransactionSet(TransactionSetCore):
    flags = TransactionSetCore._flags
    vsflags = TransactionSetCore._vsflags
    color = TransactionSetCore._color

    def run(self, callback, data, probfilter):
        log.debug('ts.run()')
        rv = TransactionSetCore.run(self, callback, data, probfilter)
        problems = self.problems()
        if rv != rpm.RPMRC_OK and problems:
            raise TransactionError(problems)
        return rv

    def check(self, *args, **kwargs):
        TransactionSetCore.check(self, *args, **kwargs)
        # NOTE: rpm.TransactionSet throws out all problems but these
        return [p for p in self.problems()
                  if p.type in (rpm.RPMPROB_CONFLICT, rpm.RPMPROB_REQUIRES)]

    def add_install(self, path, key=None, upgrade=False):
        log.debug('add_install(%s, %s, upgrade=%s)', path, key, upgrade)
        if key is None:
            key = path
        retval, header = self.hdrFromFdno(open(path))
        if retval != rpm.RPMRC_OK:
            raise rpm.error("error reading package header")
        if not self.addInstall(header, key, upgrade):
            raise rpm.error("adding package to transaction failed")

    def __del__(self):
        self.closeDB()

probtypes = { rpm.RPMPROB_NEW_FILE_CONFLICT : _('file conflicts'),
              rpm.RPMPROB_FILE_CONFLICT : _('file conflicts'),
              rpm.RPMPROB_OLDPACKAGE: _('older package(s)'),
              rpm.RPMPROB_DISKSPACE: _('insufficient disk space'),
              rpm.RPMPROB_DISKNODES: _('insufficient disk inodes'),
              rpm.RPMPROB_CONFLICT: _('package conflicts'),
              rpm.RPMPROB_PKG_INSTALLED: _('package already installed'),
              rpm.RPMPROB_REQUIRES: _('required package'),
              rpm.RPMPROB_BADARCH: _('package for incorrect arch'),
              rpm.RPMPROB_BADOS: _('package for incorrect os'),
            }

class FedupError(Exception):
    pass

class TransactionError(FedupError):
    def __init__(self, problems):
        self.problems = problems

class FedupUpgrade(object):
    def __init__(self, root='/', rpmlog=None, scriptlog=None):
        self.root = root
        self.rpmlog = rpmlog
        self.scriptlog = scriptlog
        self.ts = None

    def setup_transaction(self, pkgfiles, check_fatal=False):
        # initialize a transaction set
        self.ts = TransactionSet(self.root, rpm._RPMVSF_NOSIGNATURES)
        # populate the transaction set
        for pkg in pkgfiles:
            try:
                self.ts.add_install(pkg, upgrade=True)
            except rpm.error as e:
                log.warn('error adding pkg: %s', e)
                # TODO: error callback
        log.debug('ts.check()')
        problems = self.ts.check()
        if problems:
            log.info("problems with transaction check:")
            for p in problems:
                log.info(p)
            if check_fatal:
                raise TransactionError(problems=problems)
        log.debug('ts.order()')
        self.ts.order()
        log.debug('ts.clean()')
        self.ts.clean()
        log.debug('transaction is ready')

    def run_transaction(self, callback):
        # set up script logging
        if self.scriptlog:
            self.ts.scriptFd = open(self.scriptlog, 'w').fileno()
        if self.rpmlog:
            rpm.setLogFile(self.rpmlog)
        # run transaction
        assert callable(callback.callback)
        return self.ts.run(callback.callback, None,
                            ~rpm.RPMPROB_FILTER_DISKSPACE)

    def test_transaction(self, callback):
        self.ts.flags = rpm.RPMTRANS_FLAG_TEST
        try:
            return self.run_transaction(callback)
        finally:
            self.ts.flags &= ~rpm.RPMTRANS_FLAG_TEST
