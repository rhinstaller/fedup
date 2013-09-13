import unittest

try:
    # Python >= 3.3
    import unittest.mock as mock
except ImportError:
    import mock

# adapted from Python 3.3 Lib/unittest/mock.py
file_spec = None

def _iterate_read_data(data):
    lines = data.split('\n')
    lastline = lines.pop(-1)
    for line in lines:
        yield line+'\n'
    if lastline:
        yield lastline

def my_mock_open(mockobj=None, read_data='', exists=True):
    global file_spec
    if file_spec is None:
        import sys
        if sys.version_info[0] == 3:
            import _io
            file_spec = list(set(dir(_io.TextIOWrapper)).union(
                             set(dir(_io.BytesIO))))
        else:
            file_spec = file

    if mockobj is None:
        mockobj = mock.MagicMock(name='open', spec=open)

    if not exists:
        mockobj.side_effect = IOError(2, 'No such file or directory')

    # make __iter__ and read work
    _data = _iterate_read_data(read_data)
    def _iter():
        for line in _data:
            yield line
    def _read(*args, **kwargs):
        return ''.join(_data)

    handle = mock.MagicMock(spec=file_spec)
    handle.write.return_value = None
    handle.__enter__.return_value = handle
    handle.__iter__.side_effect = _iter
    handle.read.side_effect = _read
    mockobj.return_value = handle

    return mockobj

try:
    # mock >= 1.0
    mock_open = mock.mock_open
except AttributeError:
    mock.mock_open = my_mock_open
    mock_open = mock.mock_open
