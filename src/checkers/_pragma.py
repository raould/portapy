"""Source pragmas understood by the PortaPy checkers.

Two pragmas are supported::

    #portapy_pragma ALLOW_MODULE
    import hashlib
    ...
    #portapy_pragma ALLOW_MODULE_END hashlib

Rules:

- A pragma is a comment that stands alone on its line (indentation allowed).
- ``ALLOW_MODULE`` must be followed on the very next physical line by
  ``import <module>`` or ``import <module> as <name>``: one module, no dots,
  no other import form.
- The import binds a name: ``<module>`` for a plain import, ``<name>`` for an
  aliased one. That bound name is allowed from the import line until a
  matching ``ALLOW_MODULE_END <bound name>``, or to the end of the file if
  there is none. Uses of the bound name outside every such range are
  reported, and so are imports that bind it outside them.
- With an alias, ``<module>`` itself is allowed only in that import
  statement: ``import mymodule as mm`` allows ``mm``, never ``mymodule``.
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
_IMPORT_LINE_RE = re.compile(
    r"^[ \t]*import[ \t]+[A-Za-z_][A-Za-z0-9_]*"
    r"([ \t]+as[ \t]+[A-Za-z_][A-Za-z0-9_]*)?[ \t]*$"
)

UNKNOWN = "unknown"
NO_IMPORT = "no_import"
NOT_ALONE = "not_alone"
END_WITHOUT_START = "end_without_start"


class PragmaScan:
    """Result of scanning one source file for pragmas."""

    def __init__(self):
        # bound name -> list of [first_line, end_line, module]; end_line is
        # the line of the matching ALLOW_MODULE_END, or None when open to the
        # end of file. The bound name is the module for a plain import and
        # the alias for 'import module as alias'.
        self.ranges = {}
        self.skip_lines = set()
        # (line, column, problem) for each malformed pragma.
        self.problems = []

    @property
    def allowed_modules(self):
        return set(self.ranges)

    def allows(self, name, line):
        """True if the bound name `name` may be used on `line`."""
        return self._covering(name, line) is not None

    def allows_import(self, module, bound, line):
        """True if an import of `module` that binds `bound` is allowed on `line`:
        `line` is inside a range for `bound` that was opened for `module`."""
        span = self._covering(bound, line)
        return span is not None and span[2] == module

    def _covering(self, name, line):
        for span in self.ranges.get(name, ()):
            if line >= span[0] and (span[1] is None or line < span[1]):
                return span
        return None


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
        found = _import_on_line(lines, imports_by_line, line + 1)
        if found is None:
            result.problems.append((line, column, NO_IMPORT))
            continue
        module, bound = found
        result.skip_lines.add(line + 1)
        _open(result, bound, module, line + 1)
    return result


def _open(result, bound, module, line):
    """Open a range for `bound`, unless one is already open for the same module.
    An open range for the same name but another module ends here."""
    for span in result.ranges.get(bound, []):
        if span[1] is None:
            if span[2] == module:
                return
            span[1] = line
    result.ranges.setdefault(bound, []).append([line, None, module])


def _close(result, module, line):
    """Close the open range for `module`; False if none is open."""
    for span in result.ranges.get(module, []):
        if span[1] is None:
            span[1] = line
            return True
    return False


def _import_on_line(lines, imports_by_line, line):
    """Return (module, bound_name) if `line` is exactly `import <module>` or
    `import <module> as <name>`, else None."""
    if line > len(lines):
        return None
    if not _IMPORT_LINE_RE.match(lines[line - 1]):
        return None
    nodes = imports_by_line.get(line, [])
    if len(nodes) != 1 or not isinstance(nodes[0], ast.Import):
        return None
    aliases = nodes[0].names
    if len(aliases) != 1 or "." in aliases[0].name:
        return None
    return (aliases[0].name, aliases[0].asname or aliases[0].name)
