'''terminal.py - provides info about the size of the controlling terminal.

Set ttyfd to choose which fd to use as the controlling tty (default: stdout)

NOTE: Importing this module adds a handler for SIGWINCH so it can update 'size'
whenever the controlling tty changes size.'''

import fcntl, struct, termios, signal, warnings
from collections import namedtuple

size = None
ttyfd = 1

class winsize(namedtuple('winsize', 'rows cols')):
    '''
    The current size of the terminal.

    rows: Number of rows on the controlling terminal
    cols: Number of columns on the controlling terminal
    '''
    pass

def getsize(fd=ttyfd):
    '''Return the size of the tty attached to the given fd (default: stdin)'''
    try:
        buf = fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack('8x'))
        (rows, cols, _, _) = struct.unpack('hhhh', buf)
        size = winsize(rows, cols)
    except IOError:
        size = winsize(0, 0)
    return size

size = getsize()

# If we're being reloaded, save a reference to the old signal handler
try:
    old_handle_winch = handle_winch
except NameError:
    old_handle_winch = signal.SIG_DFL

# Update 'size' when we get SIGWINCH
def handle_winch(signum, frame):
    global size
    size = getsize()
old_handler = signal.signal(signal.SIGWINCH, handle_winch)

# Warn the user if we just clobbered an external SIGWINCH handler
if old_handler not in (signal.SIG_DFL, signal.SIG_IGN, old_handle_winch):
    if old_handler is None:
        msg = "clobbered existing non-Python SIGWINCH handler"
    else:
        msg = "clobbered existing SIGWINCH handler %s" % old_handler
    warnings.warn(msg, RuntimeWarning)
