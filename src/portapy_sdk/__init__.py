"""Small Python 2.0-compatible SDK shims for portable python programs.

Typed for mypy with type comments (Python 2.0 cannot parse annotations). The
type tags (PpyBytes, PpyAsciiBytes, ...) are defined under 'if MYPY:' below,
which mypy reads and Python never runs. See TYPES.md.
"""

import os
import sys
#portapy_pragma ALLOW_MODULE
import tempfile
#portapy_pragma ALLOW_MODULE
import binascii

#----------------------------------------

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
    f = getattr(os, 'lstat', os.stat)  # type: PpyCallable[[PpyAny], os.stat_result]
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
    # type: (PpyOptional[PpyUnion2[int, str]]) -> None
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
    # type: () -> int
    environment_level = _level_from_name(os.environ.get("PPY_PRNTLOGLEVEL"))
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
        label = "VERBOSE"
    elif numeric == PPY_DEBUG:
        label = "DEBUG"
    elif numeric == PPY_WARN:
        label = "WARN"
    else:
        label = "ERROR"
    sys.stderr.write("[portapy:%s] %s\n" % (label, message))
    sys.stderr.flush()


def prnt(*values):
    # type: (*object) -> None
    """Write values separated by spaces and terminated by a newline."""
    index = 0
    while index < len(values):
        if index != 0:
            sys.stdout.write(" ")
        sys.stdout.write("%s" % str(values[index]))
        index = index + 1
    sys.stdout.write("\n")


def write(value):
    # type: (object) -> None
    """Write one value without adding a newline."""
    sys.stdout.write("%s" % value)


def int_div(left, right):
    # type: (int, int) -> int
    """Return Python-style floor division without using `//` syntax."""
    return divmod(left, right)[0]


def current_exception():
    # type: () -> PpyOptional[BaseException]
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
    PPY_NATIVE_STR_IS_BYTES = int(bytes is str)  # type: ignore[comparison-overlap]  # Python 2: true
except NameError:
    PPY_NATIVE_STR_IS_BYTES = 1

try:
    _LONG = long  # type: ignore[name-defined]
except NameError:
    _LONG = int

_PPY_INT_TYPE = type(1)
_PPY_LONG_TYPE = type(_LONG(0))
_PPY_DICT_TYPE = type({})  # type: typing.Type[typing.Dict[typing.Any, typing.Any]]
_PPY_LIST_TYPE = type([])  # type: typing.Type[typing.List[typing.Any]]
_PPY_TUPLE_TYPE = type(())
_PPY_NATIVE_STR = type('')

if PPY_NATIVE_STR_IS_BYTES:
    _PPY_BYTES_TYPE = _PPY_NATIVE_STR  # type: typing.Type[bytes]  # type: ignore[assignment]  # Python 2: bytes is str
else:
    _PPY_BYTES_TYPE = type('x'.encode('ascii'))

try:
    _PPY_TEXT_TYPE = unicode  # type: ignore[name-defined]
except NameError:
    _PPY_TEXT_TYPE = str


# ---------------------------------------------------------------------------
# Type tags (TYPES.md).
#
# Source tags are aliases: they name values that start life as plain Python
# values (literals, sys.argv, os results). Derived tags are NewTypes: only a
# conversion makes one, or the checking constructor of the same name at a
# trust boundary (an HTTP body, decoded data). mypy reads the 'if MYPY:'
# block; Python only parses it (so it uses no annotation syntax) and runs the
# 'else:' block, where the source tags are the real per-version types and the
# derived tags are the checking functions just below.

def _check_ascii_bytes(b):
    # type: (bytes) -> bytes
    """Mark bytes as ASCII-only bytes. Raises TypeError/ValueError if they are not."""
    if type(b) != _PPY_BYTES_TYPE:
        raise TypeError("expected bytes, got %s" % type(b))
    if ascii_or_none(b) is None:
        raise ValueError("not ASCII")
    return b


def _check_bencoded(b):
    # type: (bytes) -> bytes
    """Mark bytes as bencoded data before bdecode(). Checks the type only; bdecode() checks the structure."""
    if type(b) != _PPY_BYTES_TYPE:
        raise TypeError("expected bytes, got %s" % type(b))
    return b


MYPY = 0 # hide all this from non-mypy tools.
if MYPY:
    #portapy_pragma ALLOW_MODULE
    import typing

    # Source tags.
    PpyNativeStr = str      # type of a plain '...' literal: bytes on Python 2, text on Python 3. mypy sees only Python 3.
    PpyAsciiStr = str       # a PpyNativeStr holding only ASCII: the input of a2b(), bkey()
    PpyBytes = bytes        # real bytes: str on Python 2, bytes on Python 3
    PpyText = str           # Python's text type (unicode on Python 2): code points, no encoding, contents not validated

    # Derived tags.
    PpyAsciiBytes = typing.NewType('PpyAsciiBytes', bytes)      # output of a2b()
    PpyBKey = typing.NewType('PpyBKey', PpyAsciiBytes)          # output of bkey(): a bencode dict key
    PpyBencoded = typing.NewType('PpyBencoded', bytes)          # output of bencode(), the only input to bdecode()

    # Bencode values. Sequence/Mapping are read-only, so covariant: a list of
    # any bytes tag can be encoded without copying. Decoded values are concrete
    # lists/dicts: read them with bv_list/bv_dict and the bd_get_* readers.
    PpyBValue = typing.Union[bytes, int, typing.Sequence['PpyBValue'], typing.Mapping[bytes, 'PpyBValue']]
    PpyBList = typing.List[PpyBValue]
    PpyBDict = typing.Dict[bytes, PpyBValue]

    # Generic helpers for type comments, so portable code needs no typing
    # import. Union cannot be aliased for any number of arguments: fixed arities.
    _GT = typing.TypeVar('_GT')
    _GK = typing.TypeVar('_GK')
    _GV = typing.TypeVar('_GV')
    _GR = typing.TypeVar('_GR')
    _GTs = typing.TypeVarTuple('_GTs')
    _GP = typing.ParamSpec('_GP')
    PpyList = typing.List[_GT]
    PpyDict = typing.Dict[_GK, _GV]
    PpyTuple = typing.Tuple[typing.Unpack[_GTs]]
    PpyOptional = typing.Optional[_GT]
    PpyUnion2 = typing.Union[_GT, _GK]
    PpyUnion3 = typing.Union[_GT, _GK, _GV]
    PpyCallable = typing.Callable[_GP, _GR]
    PpyAny = typing.Any
else:
    PpyNativeStr = _PPY_NATIVE_STR
    PpyAsciiStr = _PPY_NATIVE_STR
    PpyBytes = _PPY_BYTES_TYPE
    PpyText = _PPY_TEXT_TYPE
    PpyAsciiBytes = _check_ascii_bytes
    PpyBKey = _check_ascii_bytes
    PpyBencoded = _check_bencoded


# ---------------------------------------------------------------------------
# The two str <-> bytes helpers. ASCII only, strict, exact inverses.

def b_ascii(s):
    # type: (PpyAsciiStr) -> PpyAsciiBytes
    """Native ASCII str -> bytes, on every version."""
    return a2b(s)


def ascii_or_none(b):
    # type: (PpyBytes) -> PpyOptional[PpyAsciiStr]
    """Bytes -> native str if pure ASCII, else None."""
    if PPY_NATIVE_STR_IS_BYTES:
        for c in b:
            if ord(c) > 127:  # type: ignore[arg-type]  # Python 2: c is a 1-char str
                return None
        return b  # type: ignore[return-value]  # Python 2: bytes is str
    try:
        return b.decode('ascii')
    except UnicodeError:
        return None


def byte_from_int(n):
    # type: (int) -> PpyBytes
    """0..255 -> a one-byte bytes value, on every version."""
    if PPY_NATIVE_STR_IS_BYTES:
        return chr(n)  # type: ignore[return-value]  # Python 2: str is bytes
    return bytes((n,))


def require_ascii_str(s):
    # type: (PpyNativeStr) -> None
    if type(s) != _PPY_NATIVE_STR:
        raise TypeError("expected native str, got %s" % type(s))
    for c in s:
        if ord(c) > 127:
            raise ValueError("not ASCII: %r" % s)


def a2b(s):
    # type: (PpyAsciiStr) -> PpyAsciiBytes
    """Native str literal -> bytes. Python 2: no-op. Python 3: encode ASCII."""
    require_ascii_str(s)
    if PPY_NATIVE_STR_IS_BYTES:
        return s  # type: ignore[return-value]  # Python 2: str is bytes
    return PpyAsciiBytes(s.encode('ascii'))


def b2a(b):
    # type: (PpyBytes) -> PpyAsciiStr
    """Bytes -> native str. Python 2: no-op. Python 3: decode ASCII.

    Raises ValueError if b is not ASCII, on every version.
    """
    if PPY_NATIVE_STR_IS_BYTES:
        require_ascii_str(b)  # type: ignore[arg-type]  # Python 2: bytes is str
        return b  # type: ignore[return-value]
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
    # type: (object) -> int
    t = type(v)
    if t == _PPY_INT_TYPE or t == _PPY_LONG_TYPE:
        return 1
    if isinstance(v, _PPY_INT_TYPE):   # Python 3 bool
        return 1
    return 0


# ---------------------------------------------------------------------------
# Encoding (sucks!!!!!!!!!!!!!!!)

def bkey(key):
    # type: (PpyAsciiStr) -> PpyBKey
    return PpyBKey(a2b(key))
def bunkey(bkey):
    # type: (PpyBytes) -> PpyAsciiStr
    return b2a(bkey)
def bd_add(d, k, v):
    # type: (PpyBDict, PpyAsciiStr, PpyBValue) -> None
    d[bkey(k)] = v
def bd_get(d, k):
    # type: (PpyBDict, PpyAsciiStr) -> PpyBValue
    return d[bkey(k)]
def dict_to_bd(d):
    # type: (PpyDict[str, PpyAny]) -> PpyBDict
    bd = {}  # type: PpyBDict
    for k in d.keys():
        v = d[k]
        if type(v) == _PPY_DICT_TYPE:     # no 'dict' name before 2.2
            v2 = dict_to_bd(v)
            v = v2
        bd[a2b(k)] = v
    return bd
def bd_to_dict(bd):
    # type: (PpyBDict) -> PpyDict[str, PpyAny]
    d = {}  # type: PpyDict[str, PpyAny]
    for k in bd.keys():
        v = bd[k]
        if type(v) == _PPY_DICT_TYPE:     # no 'dict' name before 2.2
            d[b2a(k)] = bd_to_dict(bv_dict(v))
        else:
            d[b2a(k)] = v
    return d

# ---------------------------------------------------------------------------
# Checked readers for decoded bencode values (untrusted data from the wire).
# Each returns its argument unchanged if it has the expected shape, else
# raises TypeError, so callers never index into a value of the wrong kind.

def bv_bytes(v):
    # type: (PpyBValue) -> PpyBytes
    if type(v) != _PPY_BYTES_TYPE:
        raise TypeError("bencode value: expected bytes, got %s" % type(v))
    return v


def bv_int(v):
    # type: (PpyBValue) -> int
    if not _is_integer(v):
        raise TypeError("bencode value: expected integer, got %s" % type(v))
    return v  # type: ignore[return-value]  # _is_integer() checked it (int or long); mypy cannot narrow through it


def bv_list(v):
    # type: (PpyBValue) -> PpyBList
    if type(v) != _PPY_LIST_TYPE:
        raise TypeError("bencode value: expected list, got %s" % type(v))
    return v


def bv_dict(v):
    # type: (PpyBValue) -> PpyBDict
    if type(v) != _PPY_DICT_TYPE:
        raise TypeError("bencode value: expected dict, got %s" % type(v))
    return v


def bd_get_bytes(d, k):
    # type: (PpyBDict, PpyAsciiStr) -> PpyBytes
    return bv_bytes(bd_get(d, k))


def bd_get_int(d, k):
    # type: (PpyBDict, PpyAsciiStr) -> int
    return bv_int(bd_get(d, k))


def bd_get_list(d, k):
    # type: (PpyBDict, PpyAsciiStr) -> PpyBList
    return bv_list(bd_get(d, k))


def bd_get_dict(d, k):
    # type: (PpyBDict, PpyAsciiStr) -> PpyBDict
    return bv_dict(bd_get(d, k))


def bencode(value):
    # type: (PpyBValue) -> PpyBencoded
    parts = []  # type: PpyList[bytes]
    _encode_into(value, parts)
    return PpyBencoded(_PPY_B_EMPTY.join(parts))


def _encode_into(value, parts):
    # type: (PpyAny, PpyList[bytes]) -> None
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
                        "e.g. use a2b() to pre-convert ASCII constants" % value)
    else:
        raise TypeError("cannot bencode %s" % t)


# ---------------------------------------------------------------------------
# Decoding. Uses slices, never indexing: indexing bytes gives a 1-character
# str on Python 2 but an int on Python 3.

def bdecode(data):
    # type: (PpyBencoded) -> PpyBValue
    found = _decode_at(data, 0)
    value = found[0]  # type: PpyBValue
    if found[1] != len(data):
        raise ValueError("trailing data after bencoded value")
    return value


def _decode_at(data, pos):
    # type: (bytes, int) -> PpyTuple[PpyAny, int]
    c = data[pos:pos + 1]
    if c == _PPY_B_EMPTY:
        raise ValueError("unexpected end of data")
    if c == _PPY_B_I:
        return _decode_int(data, pos + 1)
    if c == _PPY_B_L:
        items = []  # type: PpyBList
        pos = pos + 1
        while data[pos:pos + 1] != _PPY_B_E:
            item, pos = _decode_at(data, pos)
            items.append(item)
        return (items, pos + 1)
    if c == _PPY_B_D:
        result = {}  # type: PpyBDict
        pos = pos + 1
        previous = None  # type: PpyOptional[bytes]
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
    # type: (bytes, int) -> PpyTuple[int, int]
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
    # type: (bytes) -> None
    i = 0
    while i < len(b):
        if _PPY_DIGIT_BYTES.find(b[i:i + 1]) < 0:
            raise ValueError("non-digit in bencode number")
        i = i + 1


def _decode_bytes(data, pos):
    # type: (bytes, int) -> PpyTuple[bytes, int]
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
