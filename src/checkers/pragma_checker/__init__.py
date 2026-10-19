"""Reject malformed or unknown PortaPy source pragmas."""
from typing import List
from checkers._framework import Diagnostic, Severity, add_rule, make_diagnostic
from checkers import _pragma

UNKNOWN_RULE = add_rule(
    Severity.ERROR,
    "unknown portapy pragma",
    ["#portapy_pragma ALLOW_MODULE", "#portapy_pragma ALLOW_MODULE_END <module>"],
)
NO_IMPORT_RULE = add_rule(
    Severity.ERROR,
    "ALLOW_MODULE pragma not followed by a plain 'import <module>' line",
    ["put 'import <module>' on the very next line"],
)
NOT_ALONE_RULE = add_rule(
    Severity.ERROR,
    "portapy pragma must be alone on its line",
    ["move the pragma to its own line"],
)
END_WITHOUT_START_RULE = add_rule(
    Severity.ERROR,
    "ALLOW_MODULE_END without a matching open ALLOW_MODULE",
    ["#portapy_pragma ALLOW_MODULE above the import of that module"],
)
_RULES = {
    _pragma.END_WITHOUT_START: END_WITHOUT_START_RULE,
    _pragma.UNKNOWN: UNKNOWN_RULE,
    _pragma.NO_IMPORT: NO_IMPORT_RULE,
    _pragma.NOT_ALONE: NOT_ALONE_RULE,
}


def check_source(source: str, filename: str = "<string>") -> List[Diagnostic]:
    return [
        make_diagnostic(filename, line, column, _RULES[problem])
        for (line, column, problem) in _pragma.scan(source).problems
    ]
