"""Reject imports outside the small portable module allowlist."""
import sys
import ast
from typing import List
from checkers._framework import Diagnostic, Severity, add_rule, make_diagnostic
from checkers._support import parse, node_position
from checkers import _pragma
RULE = add_rule(Severity.ERROR, "unsupported module import", ["portable allowlisted modules"])
OUT_OF_RANGE_RULE = add_rule(
    Severity.ERROR,
    "pragma-allowed module used outside its ALLOW_MODULE range",
    ["use it before #portapy_pragma ALLOW_MODULE_END <module>"],
)
ALLOWLIST = set((
    "core",
    "errors",
    "importlib",
    "math",
    "os",
    "portapy",
    "portapy_sdk",
    "result",
    "shlex",
    "shutil",
    "string",
    "sys",
    "stat",
    "time",
    "traceback",
))
def check_source(source: str, filename: str = "<string>") -> List[Diagnostic]:
    tree = parse(source)
    if tree is None:
        return []
    pragmas = _pragma.scan(source)
    found = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        if names:
            line, column = node_position(node)
            bad = list(filter(lambda n: n not in ALLOWLIST and not pragmas.allows(n, line), names))
            for b in bad:
                found.append(make_diagnostic(filename, line, column, RULE, "(module: '%s')" % b))
        elif isinstance(node, ast.Name):
            # Uses of a pragma-allowed module's name outside its range.
            if (node.id in pragmas.ranges and node.id not in ALLOWLIST
                    and not pragmas.allows(node.id, node.lineno)):
                line, column = node_position(node)
                found.append(make_diagnostic(filename, line, column, OUT_OF_RANGE_RULE))
    return found
