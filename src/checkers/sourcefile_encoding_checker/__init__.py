"""Require portable source files to be pure ASCII with no coding declaration.

Why: the bytes a literal produces depend on the interpreter and on any PEP 263
coding declaration. Python 2.0-2.2 ignores declarations and takes non-ASCII
bytes raw; 2.3-2.4 warn; 2.5+ reject non-ASCII without a declaration; Python 3
assumes UTF-8 and turns literals into text. Pure ASCII reads the same under
every ASCII-compatible encoding Python accepts, so an all-ASCII file means the
same thing on every interpreter, and a declaration is then never needed.

Rules
- Every byte of the file must be below 0x80: code, strings, comments, docstrings
  and any byte-order mark. One diagnostic per offending line, at the first
  offending byte.
- No coding declaration (PEP 263 form) on line 1 or 2.

The checker reads the file's raw bytes when the file exists, so the result does
not depend on the locale the dispatcher used to decode it. For source text
given directly (tests), it checks the characters of that text instead.
"""

import os
import re
from typing import List

from checkers._framework import Diagnostic, Severity, add_rule, make_diagnostic

NON_ASCII_RULE = add_rule(
    Severity.ERROR,
    "non-ASCII byte in source file",
    ["ASCII escape such as \\xe9 or \\u00e9", "move the text to a data file"],
)
CODING_RULE = add_rule(
    Severity.ERROR,
    "source coding declaration",
    ["remove it: pure-ASCII source needs no declaration"],
)

# PEP 263: a comment line matching this regex on line 1 or 2.
_CODING_RE = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+")


def _source_bytes(source: str, filename: str) -> bytes:
    if filename and os.path.isfile(filename):
        handle = open(filename, "rb")
        try:
            return handle.read()
        finally:
            handle.close()
    # Text given directly: any non-ASCII character becomes non-ASCII bytes.
    return source.encode("utf-8", "surrogateescape")


def check_bytes(data: bytes, filename: str = "<string>") -> List[Diagnostic]:
    """Check raw source bytes. Usable on its own, without a dispatcher."""
    found = []
    lines = data.split(b"\n")
    for index, line in enumerate(lines):
        line_number = index + 1
        for column, byte in enumerate(line):
            if byte > 0x7F:
                found.append(make_diagnostic(
                    filename, line_number, column + 1, NON_ASCII_RULE))
                break
        if line_number <= 2 and _CODING_RE.match(line):
            found.append(make_diagnostic(filename, line_number, 1, CODING_RULE))
    return found


def check_source(source: str, filename: str = "<string>") -> List[Diagnostic]:
    return check_bytes(_source_bytes(source, filename), filename)
