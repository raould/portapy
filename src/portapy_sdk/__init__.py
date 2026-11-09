"""Small Python 2.0-compatible SDK shims for portable python programs.

Typed for mypy with type comments (Python 2.0 cannot parse annotations). The
type tags (PpyBytes, PpyAsciiBytes, ...) are defined under 'if MYPY:' below,
which mypy reads and Python never runs. See TYPES.md.
"""

import os
import sys
# portapy_pragma ALLOW_MODULE
import tempfile
import binascii

# ----------------------------------------

# for python 2.0+


def sorted_list(lst, get_sort_key):
    # type: (PpyList[_GT], PpyCallable[[_GT], PpyAny]) -> PpyList[_GT]
    # 1. Decorate: build tuples of (sort_key, unique_index, original_item)
    decorated = []  # type: PpyList[PpyTuple[PpyAny, int, _GT]]
    i = 0
    for item in lst:
        sort_key = get_sort_key(item)
        decorated.append((sort_key, i, item))
        i += 1
    # 2. Sort the decorated list of tuples
    decorated.sort()
    # 3. Undecorate: extract only tuple[2] (the original item)
    result = []  # type: PpyList[_GT]
    for sort_key, index, item in decorated:
        result.append(item)
    return result

#
# Other OS functions that exotic ports may lack.
#


def get_lstat():
    # type: () -> PpyCallable[[PpyAny], os.stat_result]
    """os.lstat where it exists (Python 2 on Windows has none), else os.stat."""
    f = getattr(
        os, 'lstat', os.stat)  # type: PpyCallable[[PpyAny], os.stat_result]
    return f

# ----------------------------------------
# print and logging.


try:
    basestring  # type: ignore[used-before-def]
except NameError:
    basestring = str

PPY_VERBOSE = 10
PPY_DEBUG = 20
PPY_WARN = 30
PPY_ERROR = 40
PPY_PRNTLOG_LEVEL = None
PPY_DEFAULT_PRNTLOG_LEVEL = PPY_WARN


def _level_from_name(value):
    # type: (PpyOptional[str]) -> PpyOptional[int]
    if value is None:
        return None
    value = value.upper()
    if value == 'VERBOSE':
        return PPY_VERBOSE
    if value == 'DEBUG':
        return PPY_DEBUG
    if value == 'WARN':
        return PPY_WARN
    if value == 'ERROR':
        return PPY_ERROR
    return None


def set_prntlog_level(level):
    # type: (PpyOptional[PpyUnion2[int, str]]) -> None
    """Set or clear the programmatic PRNTLOG threshold."""
    global PPY_PRNTLOG_LEVEL
    if level is None:
        PPY_PRNTLOG_LEVEL = None
        return
    if isinstance(level, basestring):
        level = _level_from_name(level)
    if level not in (PPY_VERBOSE, PPY_DEBUG, PPY_WARN, PPY_ERROR):
        raise ValueError('invalid PRNTLOG level')
    PPY_PRNTLOG_LEVEL = level


def _effective_prntlog_level():
    # type: () -> int
    environment_level = _level_from_name(os.environ.get('PPY_PRNTLOGLEVEL'))
    if PPY_PRNTLOG_LEVEL is None:
        if environment_level is None:
            return PPY_DEFAULT_PRNTLOG_LEVEL
        return environment_level
    if environment_level is None:
        return PPY_PRNTLOG_LEVEL
    if PPY_PRNTLOG_LEVEL < environment_level:
        return PPY_PRNTLOG_LEVEL
    return environment_level


def prntlog(level, message):
    # type: (PpyUnion2[int, str], object) -> None
    """Write a gated diagnostic to stderr."""
    if isinstance(level, basestring):
        numeric = _level_from_name(level)
    else:
        numeric = level
    if numeric is None or numeric < _effective_prntlog_level():
        return
    if numeric == PPY_VERBOSE:
        label = 'VERBOSE'
    elif numeric == PPY_DEBUG:
        label = 'DEBUG'
    elif numeric == PPY_WARN:
        label = 'WARN'
    else:
        label = 'ERROR'
    sys.stderr.write('[portapy:%s] %s\n' % (label, message))
    sys.stderr.flush()


def prnt(*values):
    # type: (*object) -> None
    """Write values separated by spaces and terminated by a newline."""
    index = 0
    while index < len(values):
        if index != 0:
            sys.stdout.write(' ')
        sys.stdout.write('%s' % str(values[index]))
        index = index + 1
    sys.stdout.write('\n')


def write(value):
    # type: (object) -> None
    """Write one value without adding a newline."""
    sys.stdout.write('%s' % value)


def int_div(left, right):
    # type: (int, int) -> int
    """Return Python-style floor division without using `//` syntax."""
    return divmod(left, right)[0]


def current_exception():
    # type: () -> PpyOptional[BaseException]
    """Return the active exception value inside an except block."""
    return sys.exc_info()[1]
