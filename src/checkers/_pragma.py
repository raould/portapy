"""Source pragmas understood by the PortaPy checkers.

Two pragmas are supported::

    #portapy_pragma ALLOW_MODULE
    import hashlib
    ...
    #portapy_pragma ALLOW_MODULE_END hashlib

Rules:

- A pragma is a comment that stands alone on its line (indentation allowed).
- ``ALLOW_MODULE`` must be followed on the very next physical line by a plain
  ``import <module>`` statement: one module, no dots, no ``as`` alias, no
  other import form.
- The module is allowed from that import line until a matching
  ``ALLOW_MODULE_END <module>``, or to the end of the file if there is none.
  Imports and uses of the module's name outside every such range are reported.
- Diagnostics from any checker on the pragma's import line are suppressed.

Anything that starts with ``#portapy_pragma`` but does not follow these rules
is reported, so a typo can never silently disable checking.
"""

import ast
import re
import tokenize

from checkers._support import parse, tokens

PRAGMA_PREFIX = "#portapy_pragma"
_ALLOW_MODULE_RE = re.compile(r"^#portapy_pragma ALLOW_MODULE\s*$")
_ALLOW_MODULE_END_RE = re.compile(
    r"^#portapy_pragma ALLOW_MODULE_END ([A-Za-z_][A-Za-z0-9_]*)\s*$"
)
_IMPORT_LINE_RE = re.compile(r"^[ \t]*import[ \t]+[A-Za-z_][A-Za-z0-9_]*[ \t]*$")

UNKNOWN = "unknown"
NO_IMPORT = "no_import"
NOT_ALONE = "not_alone"
END_WITHOUT_START = "end_without_start"


class PragmaScan:
    """Result of scanning one source file for pragmas."""

    def __init__(self):
        # module -> list of [first_line, end_line]; end_line is the line of
        # the matching ALLOW_MODULE_END, or None when open to end of file.
        self.ranges = {}
        self.skip_lines = set()
        # (line, column, problem) for each malformed pragma.
        self.problems = []

    @property
    def allowed_modules(self):
        return set(self.ranges)

    def allows(self, module, line):
        """True if `module` may be imported or used on `line`."""
        for first, end in self.ranges.get(module, ()):
            if line >= first and (end is None or line < end):
                return True
        return False


def scan(source):
    """Return the pragmas found in source text."""
    result = PragmaScan()
    lines = source.splitlines()
    tree = parse(source)
    imports_by_line = {}
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports_by_line.setdefault(node.lineno, []).append(node)

    for token in tokens(source):
        if token.type != tokenize.COMMENT:
            continue
        text = token.string
        if not text.startswith(PRAGMA_PREFIX):
            continue
        line, column = token.start[0], token.start[1] + 1
        if lines[line - 1].strip() != text.strip():
            result.problems.append((line, column, NOT_ALONE))
            continue
        end_match = _ALLOW_MODULE_END_RE.match(text)
        if end_match:
            if not _close(result, end_match.group(1), line):
                result.problems.append((line, column, END_WITHOUT_START))
            continue
        if not _ALLOW_MODULE_RE.match(text):
            result.problems.append((line, column, UNKNOWN))
            continue
        module = _plain_import_on_line(lines, imports_by_line, line + 1)
        if module is None:
            result.problems.append((line, column, NO_IMPORT))
            continue
        result.skip_lines.add(line + 1)
        open_ranges = [r for r in result.ranges.get(module, []) if r[1] is None]
        if not open_ranges:
            result.ranges.setdefault(module, []).append([line + 1, None])
    return result


def _close(result, module, line):
    """Close the open range for `module`; False if none is open."""
    for span in result.ranges.get(module, []):
        if span[1] is None:
            span[1] = line
            return True
    return False


def _plain_import_on_line(lines, imports_by_line, line):
    """Return the module name if `line` is exactly `import <module>`."""
    if line > len(lines):
        return None
    if not _IMPORT_LINE_RE.match(lines[line - 1]):
        return None
    nodes = imports_by_line.get(line, [])
    if len(nodes) != 1 or not isinstance(nodes[0], ast.Import):
        return None
    aliases = nodes[0].names
    if len(aliases) != 1 or aliases[0].asname is not None:
        return None
    if "." in aliases[0].name:
        return None
    return aliases[0].name
