"""Small Python 2.0-compatible SDK shims for portable python programs."""

import os
import sys
#portapy_pragma ALLOW_MODULE
import tempfile
#portapy_pragma ALLOW_MODULE
import binascii

#----------------------------------------

# for python 2.0+
def sorted_list(lst, get_sort_key):
    # 1. Decorate: build tuples of (sort_key, unique_index, original_item)
    decorated = []
    i = 0
    for item in lst:
        sort_key = get_sort_key(item)
        decorated.append((sort_key, i, item))
        i += 1
    # 2. Sort the decorated list of tuples
    decorated.sort()
    # 3. Undecorate: extract only tuple[2] (the original item)
    result = []
    for sort_key, index, item in decorated:
        result.append(item)
    return result

#
# Other OS functions that exotic ports may lack.
#

def get_lstat():
    """os.lstat where it exists (Python 2 on Windows has none), else os.stat."""
    return getattr(os, 'lstat', os.stat)

# ----------------------------------------
# print and logging.

try:
    basestring
except NameError:
    basestring = str

PPY_VERBOSE = 10
PPY_DEBUG = 20
PPY_WARN = 30
PPY_ERROR = 40
PPY_PRNTLOG_LEVEL = None
PPY_DEFAULT_PRNTLOG_LEVEL = PPY_WARN


def _level_from_name(value):
    if value is None:
        return None
    value = value.upper()
    if value == "VERBOSE":
        return PPY_VERBOSE
    if value == "DEBUG":
        return PPY_DEBUG
    if value == "WARN":
        return PPY_WARN
    if value == "ERROR":
        return PPY_ERROR
    return None


def set_prntlog_level(level):
    """Set or clear the programmatic PRNTLOG threshold."""
    global PPY_PRNTLOG_LEVEL
    if level is None:
        PPY_PRNTLOG_LEVEL = None
        return
    if isinstance(level, basestring):
        level = _level_from_name(level)
    if level not in (PPY_VERBOSE, PPY_DEBUG, PPY_WARN, PPY_ERROR):
        raise ValueError("invalid PRNTLOG level")
    PPY_PRNTLOG_LEVEL = level


def _effective_prntlog_level():
    environment_level = _level_from_name(
        __import__("os").environ.get("PPY_PRNTLOGLEVEL")
    )
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
    """Write a gated diagnostic to stderr."""
    if isinstance(level, basestring):
        level = _level_from_name(level)
    if level is None or level < _effective_prntlog_level():
        return
    if level == PPY_VERBOSE:
        label = "VERBOSE"
    elif level == PPY_DEBUG:
        label = "DEBUG"
    elif level == PPY_WARN:
        label = "WARN"
    else:
        label = "ERROR"
    sys.stderr.write("[portapy:%s] %s\n" % (label, message))
    sys.stderr.flush()


def prnt(*values):
    """Write values separated by spaces and terminated by a newline."""
    index = 0
    while index < len(values):
        if index != 0:
            sys.stdout.write(" ")
        sys.stdout.write("%s" % str(values[index]))
        index = index + 1
    sys.stdout.write("\n")


def write(value):
    """Write one value without adding a newline."""
    sys.stdout.write("%s" % value)


def int_div(left, right):
    """Return Python-style floor division without using `//` syntax."""
    return divmod(left, right)[0]


def current_exception():
    """Return the active exception value inside an except block."""
    return sys.exc_info()[1]

# ---------------------------------------------------------------------------

"""Plain bencode, both directions, portable from Python 2.0 to 3.x.

Standard BitTorrent bencode: any bencode library can read and write it.

  integer      i<decimal>e          any size
  byte string  <length>:<bytes>     binary-safe, no escaping
  list         l<items>e
  dict         d<key><value>...e    keys are byte strings, sorted

Everything string-like is bytes, keys included. Bytes are the native str on
Python 2 and bytes on Python 3. To write keys and other ASCII constants the
same way on every version, use the two helpers:

  to_bytes('length')   native str literal -> bytes   (Py2: no-op)
  to_str(b)            bytes -> native str           (Py2: no-op)

Both are ASCII-only and strict, so they give identical results on every
version and fail loudly on anything else. Encoding is canonical (sorted
keys), so the same value always gives the same bytes on every interpreter.
"""

try:
    PPY_NATIVE_STR_IS_BYTES = (bytes is str)
except NameError:
    PPY_NATIVE_STR_IS_BYTES = 1

try:
    _LONG = long
except NameError:
    _LONG = int

_PPY_INT_TYPE = type(1)
_PPY_LONG_TYPE = type(_LONG(0))
_PPY_DICT_TYPE = type({})
_PPY_LIST_TYPE = type([])
_PPY_TUPLE_TYPE = type(())
_PPY_NATIVE_STR = type('')

if PPY_NATIVE_STR_IS_BYTES:
    _PPY_BYTES_TYPE = _PPY_NATIVE_STR
else:
    _PPY_BYTES_TYPE = type('x'.encode('ascii'))


# ---------------------------------------------------------------------------
# The two str <-> bytes helpers. ASCII only, strict, exact inverses.

def b_ascii(s):
    """Native ASCII str -> bytes, on every version."""
    if PPY_NATIVE_STR_IS_BYTES:
        return s
    return s.encode('ascii')


def ascii_or_none(b):
    """Bytes -> native str if pure ASCII, else None."""
    if PPY_NATIVE_STR_IS_BYTES:
        for c in b:
            if ord(c) > 127:
                return None
        return b
    try:
        return b.decode('ascii')
    except UnicodeError:
        return None


def byte_from_int(n):
    """0..255 -> a one-byte bytes value, on every version."""
    if PPY_NATIVE_STR_IS_BYTES:
        return chr(n)
    return bytes((n,))


def require_ascii_str(s):
    if type(s) != _PPY_NATIVE_STR:
        raise TypeError("expected native str, got %s" % type(s))
    for c in s:
        if ord(c) > 127:
            raise ValueError("not ASCII: %r" % s)


def a2b(s):
    """Native str literal -> bytes. Python 2: no-op. Python 3: encode ASCII."""
    require_ascii_str(s)
    if PPY_NATIVE_STR_IS_BYTES:
        return s
    return s.encode('ascii')


def b2a(b):
    """Bytes -> native str. Python 2: no-op. Python 3: decode ASCII.

    Raises ValueError if b is not ASCII, on every version.
    """
    if PPY_NATIVE_STR_IS_BYTES:
        require_ascii_str(b)
        return b
    if type(b) != _PPY_BYTES_TYPE:
        raise TypeError("expected bytes, got %s" % type(b))
    try:
        return b.decode('ascii')
    except UnicodeError:
        raise ValueError("not ASCII")


_PPY_B_I = a2b('i')
_PPY_B_L = a2b('l')
_PPY_B_D = a2b('d')
_PPY_B_E = a2b('e')
_PPY_B_COLON = a2b(':')
_PPY_B_MINUS = a2b('-')
_PPY_B_ZERO = a2b('0')
_PPY_B_EMPTY = a2b('')
_PPY_DIGIT_BYTES = a2b('0123456789')


def _is_integer(v):
    t = type(v)
    if t == _PPY_INT_TYPE or t == _PPY_LONG_TYPE:
        return 1
    return isinstance(v, _PPY_INT_TYPE)   # Python 3 bool


# ---------------------------------------------------------------------------
# Encoding (sucks!!!!!!!!!!!!!!!)

def bkey(key):
    return a2b(key)
def bunkey(bkey):
    return b2a(bkey)
def bd_add(d, k, v):
    d[bkey(k)] = v
def bd_get(d, k):
    return d[bkey(k)]
def dict_to_bd(d):
    bd = {}
    for k in d.keys():
        v = d[k]
        if type(v) == _PPY_DICT_TYPE:     # no 'dict' name before 2.2
            v2 = dict_to_bd(v)
            v = v2
        bd[a2b(k)] = v
    return bd
def bd_to_dict(bd):
    d = {}
    for k in bd.keys():
        v = bd[k]
        if type(v) == _PPY_DICT_TYPE:     # no 'dict' name before 2.2
            v2 = bd_to_dict(v)
            v = v2
        d[b2a(k)] = v
    return d

def bencode(value):
    parts = []
    _encode_into(value, parts)
    return _PPY_B_EMPTY.join(parts)


def _encode_into(value, parts):
    t = type(value)
    if t == _PPY_BYTES_TYPE:
        parts.append(a2b('%d:' % len(value)))
        parts.append(value)
    elif _is_integer(value):
        parts.append(a2b('i%de' % value))
    elif t == _PPY_LIST_TYPE or t == _PPY_TUPLE_TYPE:
        parts.append(_PPY_B_L)
        for item in value:
            _encode_into(item, parts)
        parts.append(_PPY_B_E)
    elif t == _PPY_DICT_TYPE:
        keys = list(value.keys())
        for k in keys:
            if type(k) != _PPY_BYTES_TYPE:
                raise TypeError("bencode dict keys must be bytes; "
                                "use a2b('name')")
        keys.sort()
        parts.append(_PPY_B_D)
        for k in keys:
            _encode_into(k, parts)
            _encode_into(value[k], parts)
        parts.append(_PPY_B_E)
    elif t == _PPY_NATIVE_STR:
        # Only reachable on Python 3: text where bytes are required.
        raise TypeError("str value %r: bencode strings are bytes; "
                        "use a2b() for ASCII constants" % value)
    else:
        raise TypeError("cannot bencode %s" % t)


# ---------------------------------------------------------------------------
# Decoding. Uses slices, never indexing: indexing bytes gives a 1-character
# str on Python 2 but an int on Python 3.

def bdecode(data):
    value, end = _decode_at(data, 0)
    if end != len(data):
        raise ValueError("trailing data after bencoded value")
    return value


def _decode_at(data, pos):
    c = data[pos:pos + 1]
    if c == _PPY_B_EMPTY:
        raise ValueError("unexpected end of data")
    if c == _PPY_B_I:
        return _decode_int(data, pos + 1)
    if c == _PPY_B_L:
        items = []
        pos = pos + 1
        while data[pos:pos + 1] != _PPY_B_E:
            item, pos = _decode_at(data, pos)
            items.append(item)
        return (items, pos + 1)
    if c == _PPY_B_D:
        result = {}
        pos = pos + 1
        previous = None
        while data[pos:pos + 1] != _PPY_B_E:
            key, pos = _decode_at(data, pos)
            if type(key) != _PPY_BYTES_TYPE:
                raise ValueError("bencode dict key is not a byte string")
            if previous is not None and not (previous < key):
                raise ValueError("bencode dict keys not sorted or repeated")
            previous = key
            value, pos = _decode_at(data, pos)
            result[key] = value
        return (result, pos + 1)
    if _PPY_DIGIT_BYTES.find(c) >= 0:
        return _decode_bytes(data, pos)
    raise ValueError("bad bencode type at offset %d" % pos)


def _decode_int(data, pos):
    end = data.find(_PPY_B_E, pos)
    if end < 0:
        raise ValueError("unterminated integer")
    digits = data[pos:end]
    body = digits
    if body[:1] == _PPY_B_MINUS:
        body = body[1:]
        if body == _PPY_B_ZERO:
            raise ValueError("negative zero in bencode integer")
    if body == _PPY_B_EMPTY:
        raise ValueError("empty bencode integer")
    if len(body) > 1 and body[:1] == _PPY_B_ZERO:
        raise ValueError("leading zero in bencode integer")
    _require_digits(body)
    return (_LONG(b2a(digits)), end + 1)


def _require_digits(b):
    i = 0
    while i < len(b):
        if _PPY_DIGIT_BYTES.find(b[i:i + 1]) < 0:
            raise ValueError("non-digit in bencode number")
        i = i + 1


def _decode_bytes(data, pos):
    colon = data.find(_PPY_B_COLON, pos)
    if colon < 0:
        raise ValueError("unterminated string length")
    length_digits = data[pos:colon]
    if length_digits == _PPY_B_EMPTY:
        raise ValueError("empty string length")
    _require_digits(length_digits)
    if len(length_digits) > 1 and length_digits[:1] == _PPY_B_ZERO:
        raise ValueError("leading zero in string length")
    length = _LONG(b2a(length_digits))
    start = colon + 1
    end = start + length
    if end > len(data):
        raise ValueError("string runs past end of data")
    return (data[start:end], end)
