import logging

class Formatter(logging.Formatter):
    levelsyms = {
        logging.DEBUG:   '(DD)',
        logging.INFO:    '(II)',
        logging.WARNING: '(WW)',
        logging.ERROR:   '(EE)',
        logging.CRITICAL:'(CC)',
        logging.FATAL:   '(FF)',
    }

    defaultfmt="[%(reltime)10.3f] %(levelsym)s %(name)s:%(funcName)s() %(message)s"
    def __init__(self, fmt=None, datefmt=None):
        if fmt is None:
            fmt = self.defaultfmt
        logging.Formatter.__init__(self, fmt, datefmt)

    def format(self, record):
        record.reltime = float(record.relativeCreated / 1000)
        record.levelsym = self.levelsyms.get(record.levelno, '(--)')
        return logging.Formatter.format(self, record)

def debuglog(filename, loggername="fedup"):
    h = logging.FileHandler(filename)
    h.setLevel(logging.DEBUG)
    h.setFormatter(Formatter())
    logger = logging.getLogger(loggername)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(h)

def consolelog(level=logging.WARNING, loggername="fedup", tty=None):
    h = logging.StreamHandler(tty)
    h.setLevel(level)
    formatter = logging.Formatter('%(name)s %(levelname)s: %(message)s')
    h.setFormatter(formatter)
    logger = logging.getLogger(loggername)
    logger.addHandler(h)
