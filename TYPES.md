# Ppy type tags

Portable code moves values between Python's string kinds, and those kinds mean
different things on Python 2 and Python 3. The Ppy tags give each kind a name,
so a reader can see what a value is, and so mypy can check that every
conversion is connected the right way round.

The tags are defined in `src/portapy_sdk/__init__.py` itself, under an
`if MYPY:` block. mypy treats a variable named `MYPY` as always true, so it
reads the block. Python 2.0 only parses it, since `MYPY = 0`, and runs the
`else:` branch instead. There are no `.pyi` stub files, so nothing can drift:
the definitions, the runtime counterparts and the code that uses them are all
in the same file, and mypy checks the SDK's own code too.

Code uses the tags in **type comments**, through the module it already
imports, so it never needs to import `typing`:

```python
import portapy_sdk as ppy

def key_for(name):
    # type: (ppy.PpyAsciiStr) -> ppy.PpyBKey
    return ppy.bkey(name)

e = {}  # type: ppy.PpyBDict
```

Projects built on portapy add their own tags with their own prefix. For example,
pybak uses `Pk`: `PkOsName`, `PkWireName`, `PkHexPath`.

## Source tags (aliases)

These name values that start life as plain Python values: literals,
`sys.argv`, the results of `os` functions. They can't be enforced, but they
show by eye what a value is, and that its meaning changes between versions. At
runtime each is the real type for that interpreter, so
`type(x) == ppy.PpyBytes` works.

| tag | meaning | Python 2 | Python 3 |
|---|---|---|---|
| `PpyNativeStr` | the type of a plain `'...'` literal | bytes (`str`) | text (`str`) |
| `PpyAsciiStr` | a `PpyNativeStr` holding only ASCII: the input of `a2b`, `bkey` | bytes | text |
| `PpyBytes` | real bytes | `str` | `bytes` |
| `PpyText` | Python's text type | `unicode` | `str` |

`PpyText` is a sequence of code points. It has no encoding; encodings only
exist for bytes. Its contents are not validated: it may hold lone surrogates
(Python 3's surrogateescape, NTFS names), surrogate pairs on narrow builds
(always on Python 2 for Windows), and either normalization form (NFC or NFD).
Refinements such as `PpyValidText` or `PpyNfcText` can be added later.

mypy checks as Python 3, so to mypy `PpyNativeStr` is simply `str`. The tag
can't make mypy see Python 2's meaning. That is what the Docker matrix and
contract tests are for.

## Derived tags (NewTypes)

These are produced only by a portapy conversion. mypy refuses a plain `bytes`
where one of them is required, which catches a missing conversion. At a trust
boundary, such as an HTTP body, the constructor of the same name marks a plain
value. At runtime it checks the value and returns it unchanged.

| tag | made by | constructor checks |
|---|---|---|
| `PpyAsciiBytes` | `a2b()`, `b_ascii()` | bytes, ASCII only |
| `PpyBKey` | `bkey()` | bytes, ASCII only |
| `PpyBencoded` | `bencode()` | bytes (`bdecode()` checks the structure) |

## Bencode values

| tag | meaning |
|---|---|
| `PpyBValue` | bytes, an integer, a sequence (list or tuple) of `PpyBValue`, or a mapping (dict) from bytes to `PpyBValue`. Sequence and mapping rather than list and dict, so typed lists such as `List[PpyAsciiBytes]` are accepted without copying |
| `PpyBList` | a list of `PpyBValue` |
| `PpyBDict` | a dict from bytes to `PpyBValue` |

`bdecode()` returns a `PpyBValue`, and mypy won't let code index into it
unchecked. Decoded data comes from the wire, so read it with the checked
readers. Each returns its argument unchanged if it has the expected shape, and
raises `TypeError` otherwise:

- `bv_bytes`, `bv_int`, `bv_list`, `bv_dict`: check one value;
- `bd_get_bytes`, `bd_get_int`, `bd_get_list`, `bd_get_dict`: read a key from a `PpyBDict` and check it.

```python
reply = ppy.bv_dict(ppy.bdecode(ppy.PpyBencoded(http_body)))
for w in ppy.bd_get_list(reply, 'entries'):
    offset = ppy.bd_get_int(ppy.bv_dict(w), 'offset')
```

## Helpers for type comments

`PpyList[T]`, `PpyDict[K, V]`, `PpyTuple[A, B, ...]`, `PpyOptional[T]`,
`PpyUnion2[A, B]`, `PpyUnion3[A, B, C]`, `PpyCallable[[A, B], R]` and
`PpyAny` are `typing`'s generics, re-exported so that type comments never need
`from typing import`, which Python 2.0 can't run. They exist only for mypy, inside the `if MYPY:` block.
`Union` can't be aliased for any number of arguments, so it comes in fixed
arities.

## Defining tags in your own project

A project's own tags follow the same pattern in one module of its own:

```python
MYPY = 0
if MYPY:
    #portapy_pragma ALLOW_MODULE
    import typing
    PkWireName = typing.NewType('PkWireName', bytes)
    PkOpened = typing.TypedDict('PkOpened', {'fp': typing.Any, 'err': typing.Optional[int]})
    class PkOsName: pass          # opaque: usable only through your own functions
else:
    PkWireName = _check_wire_name # a checking function defined above the block
```

Everything in the block must still parse on Python 2.0. That means no
annotation syntax: write `TypedDict` in its call form, and `NewType`, generic
aliases and plain classes as ordinary expressions and statements.

Where code makes an assumption mypy can't check, such as a Python-2-only line
or a value checked by a function mypy can't see into, it carries a
`# type: ignore[code]` with the reason on the same line. `grep "type: ignore"`
lists every such place.

## Checking

```sh
MYPYPATH=src mypy --strict your_module.py
```

`test/test_sdk_types.py` runs four checks. The mypy ones are skipped when
mypy isn't installed.

- **The runtime tags:** the source tags are the real types, and the constructors and checked readers accept and reject the right values.
- **Portability:** `test/types/good_client.py` and `test/types/bad_client.py` pass portapy.
- **mypy on the SDK itself:** `portapy_sdk/__init__.py` is clean under `--strict`.
- **mypy on the samples:** `good_client.py` is clean under `--strict`, and `bad_client.py` errors exactly on its lines marked `# EXPECT-ERROR`.
