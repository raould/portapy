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

#----------------------------------------
# Filename strategy.

"""
Portable from Python 2.0 to 3.x. No version checks and no OS-name checks:
every choice is a feature test, made once at startup by choose_naming().

A strategy is a tuple:

    (name_kind, argv_to_native, name_to_raw)

- name_kind       recorded in the manifest header; tells the server how to
                  decode names for display.
- argv_to_native  converts a sys.argv root into the native path type that
                  the strategy walks with (bytes or text).
- name_to_bytes     converts one os.listdir() entry into raw bytes for hexing.

os.listdir() returns names of the same type as its argument, so once the
root is converted, the walk itself never converts anything except through
name_to_bytes.
"""

#
# Feature flags, computed once.
# Many of these are just for pybak.
#

# Is the native str type already bytes? Python 2: yes. Python 3: no.
try:
    PPY_NATIVE_STR_IS_BYTES = (bytes is str)
except NameError:
    PPY_NATIVE_STR_IS_BYTES = 1

_PPY_NATIVE_STR = type('')

# Python 2's text type, or None on Python 3.
try:
    _PPY_UNICODE = unicode
except NameError:
    _PPY_UNICODE = None

# Code point -> one-character text, on every version.
try:
    _PPY_UNICHR = unichr
except NameError:
    _PPY_UNICHR = chr

_PPY_NATIVE_BYTES = 'native-bytes'      # names are the filesystem's own bytes
_PPY_WIN_UTF8 = 'win-utf8'              # Windows names as UTF-8 bytes (PEP 529)
_PPY_WIN_UTF16LE = 'win-utf16le'        # Windows names as UTF-16LE code units
_PPY_WIN_CODEPAGE = 'win-codepage'      # Windows names via ANSI code page: LOSSY


#
# Feature probes.
#

def interpreter_name_codec():
    """The codec this interpreter uses for ALL OS names, lowercased.

    This is sys.getfilesystemencoding(), whose Python name is misleading: it
    does not inspect any filesystem or mount. It is one process-wide setting,
    chosen at startup (POSIX: from the locale or UTF-8 mode; Windows: 'mbcs'
    or 'utf-8'; macOS: 'utf-8'), telling how Python converts between its text
    type and the bytes the OS API uses for names. It says nothing about the
    encoding of names on a particular disk. Returns None before Python 2.3.
    """
    getter = getattr(sys, 'getfilesystemencoding', None)
    if getter is None:
        return None
    enc = getter()
    if enc is None:
        return None
    return enc.lower()


def has_win32_core():
    """True if Python is running on the Win32 API family (nt or ce core)."""
    names = sys.builtin_module_names
    return ('nt' in names) or ('ce' in names)


def unicode_filenames_supported():
    """True if the OS layer accepts text paths without a code page (2.3+)."""
    return getattr(os.path, 'supports_unicode_filenames', 0)


def is_utf8_name(enc):
    return enc == 'utf-8' or enc == 'utf8'


#
# Root converters: sys.argv entry -> native path for the walk.
#

def argv_to_bytes(arg):
    """Root as raw bytes. Python 2 argv is already bytes."""
    if PPY_NATIVE_STR_IS_BYTES:
        return arg
    fsencode = getattr(os, 'fsencode', None)      # 3.2+
    if fsencode is not None:
        return fsencode(arg)
    enc = interpreter_name_codec()
    try:
        return arg.encode(enc, 'surrogateescape')  # 3.1
    except LookupError:
        return arg.encode(enc)                     # 3.0


def argv_to_text(arg):
    """Root as text, for the UTF-16 strategy.

    Python 2 argv on Windows is code-page bytes: characters outside the code
    page have already become '?'. Refuse rather than walk the wrong path.
    """
    if _PPY_UNICODE is not None and type(arg) == _PPY_NATIVE_STR:
        text = _PPY_UNICODE(arg, 'mbcs')
        if contains_question_mark(text):
            raise ValueError(
                "root path contains '?': its real name was lost by the "
                "Windows code page before Python saw it; pass a path "
                "without non-code-page characters")
        return text
    return arg


def argv_identity(arg):
    return arg


def contains_question_mark(text):
    for c in text:
        if ord(c) == 63:
            return 1
    return 0


#
# Name converters: one os.listdir() entry -> raw bytes.
#

def name_identity(name):
    """The entry is already raw bytes."""
    return name


def name_to_utf16le(name):
    """Text entry -> UTF-16LE code units as bytes, lone surrogates kept."""
    try:
        return name.encode('utf-16-le', 'surrogatepass')   # 3.1+
    except LookupError:
        return name.encode('utf-16-le')   # Python 2 never rejects surrogates


#
# Strategy selection.
#

def choose_naming():
    """
    This is currently mainly just for pybak.
    Return (name_kind, argv_to_native, name_to_bytes) for this interpreter.
    name_kind: NATIVE_BYTES, WIN_UTF8, WIN_UTF16LE, WIN_CODEPAGE.
    argv_to_native: convert sys.argv input to a type to pass to os.listdir.
    name_to_bytes: convert path names from os.listdir into byte equivalent.
    """
    enc = interpreter_name_codec()
    win32 = has_win32_core()
    if enc is None:
        # Python 2.0-2.2: no way to ask; the Win32 core means code pages.
        if win32:
            return (_PPY_WIN_CODEPAGE, argv_identity, name_identity)
        return (_PPY_NATIVE_BYTES, argv_to_bytes, name_identity)
    if enc == 'mbcs':
        # Python converts names through the ANSI code page: bytes API lossy.
        if unicode_filenames_supported():
            return (_PPY_WIN_UTF16LE, argv_to_text, name_to_utf16le)
        return (_PPY_WIN_CODEPAGE, argv_identity, name_identity)
    if win32 and is_utf8_name(enc):
        return (_PPY_WIN_UTF8, argv_to_bytes, name_identity)   # PEP 529, 3.6+
    return (_PPY_NATIVE_BYTES, argv_to_bytes, name_identity)


def is_lossy(name_kind):
    return name_kind == _PPY_WIN_CODEPAGE


#
# Other OS functions that exotic ports may lack.
#

def get_lstat():
    """os.lstat where it exists (Python 2 on Windows has none), else os.stat."""
    return getattr(os, 'lstat', os.stat)


#
# Active self-test: confirm the chosen strategy really round-trips names.
#

def make_bytes(ints):
    if PPY_NATIVE_STR_IS_BYTES:
        chars = []
        for i in ints:
            chars.append(chr(i))
        return ''.join(chars)
    return bytes(ints)


def probe_text():
    """'probe-' + e-acute + a character above U+FFFF, as text."""
    text = 'probe-'
    if _PPY_UNICODE is not None:
        text = _PPY_UNICODE(text)
    text = text + _PPY_UNICHR(0xe9)
    try:
        text = text + _PPY_UNICHR(0x1f600)
    except ValueError:
        # Narrow Python 2 build: write the surrogate pair explicitly.
        text = text + _PPY_UNICHR(0xd83d) + _PPY_UNICHR(0xde00)
    return text


# UTF-8 bytes of probe_text(): "probe-" + C3 A9 + F0 9F 98 80
_PPY_PROBE_UTF8 = (0x70, 0x72, 0x6f, 0x62, 0x65, 0x2d,
              0xc3, 0xa9, 0xf0, 0x9f, 0x98, 0x80)


def make_temp_dir():
    mkdtemp = getattr(tempfile, 'mkdtemp', None)      # 2.3+
    if mkdtemp is not None:
        return mkdtemp()
    path = tempfile.mktemp()
    os.mkdir(path)
    return path


def self_test_naming(strategy):
    """Create a probe file in a temp dir and check the strategy round-trips it.

    Returns (ok, message). ok is 1 or 0. Never touches the user's folders.
    Exact bytes may differ on normalizing filesystems (e.g. HFS+ NFD); that
    is reported as information, not failure, as long as the listed name
    re-opens the same file.
    """
    name_kind = strategy[0]
    argv_to_native = strategy[1]
    name_to_bytes = strategy[2]
    if is_lossy(name_kind):
        return (0, "lossy strategy %s: no round-trip possible" % name_kind)
    temp_dir = make_temp_dir()
    try:
        result = _probe(temp_dir, name_kind, argv_to_native, name_to_bytes)
    finally:
        _remove_tree_one_level(temp_dir)
    return result


def _probe(temp_dir, name_kind, argv_to_native, name_to_bytes):
    native_dir = argv_to_native(temp_dir)
    if name_kind == _PPY_WIN_UTF16LE:
        created = probe_text()
        expected_raw = name_to_utf16le(created)
    else:
        created = make_bytes(_PPY_PROBE_UTF8)
        expected_raw = created
    marker = make_bytes((0x70, 0x79, 0x62, 0x61, 0x6b))   # "pybak"
    try:
        handle = open(os.path.join(native_dir, created), 'wb')
        try:
            handle.write(marker)
        finally:
            handle.close()
    except (IOError, OSError, UnicodeError):
        return (0, "cannot create probe file with strategy %s" % name_kind)
    entries = os.listdir(native_dir)
    if len(entries) != 1:
        return (0, "expected 1 probe entry, found %d" % len(entries))
    listed = entries[0]
    raw = name_to_bytes(listed)
    handle = open(os.path.join(native_dir, listed), 'rb')
    try:
        content = handle.read()
    finally:
        handle.close()
    if content != marker:
        return (0, "listed name did not re-open the probe file")
    if raw != expected_raw:
        return (1, "ok; filesystem changed the name bytes "
                   "(normalizing filesystem)")
    return (1, "ok")


def _remove_tree_one_level(path):
    # The temp dir holds only probe files; remove them, then the dir.
    # Listing with the same type as `path` keeps the joined paths valid.
    for name in os.listdir(path):
        try:
            os.remove(os.path.join(path, name))
        except (IOError, OSError):
            pass
    try:
        os.rmdir(path)
    except (IOError, OSError):
        pass


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
    if t == _PPY_INT_TYPE or t == _LONG:
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
