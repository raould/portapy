"""Tests for the #portapy_pragma ALLOW_MODULE source pragma."""

import os
import sys
import tempfile
import unittest


PORTAPY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT_DIR = os.path.join(PORTAPY_DIR, "scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import checkall  # noqa: E402
from checkers import module_import_checker, pragma_checker  # noqa: E402

IMPORT_ID = module_import_checker.RULE[0]
OUT_OF_RANGE_ID = module_import_checker.OUT_OF_RANGE_RULE[0]
END_WITHOUT_START_ID = pragma_checker.END_WITHOUT_START_RULE[0]
UNKNOWN_ID = pragma_checker.UNKNOWN_RULE[0]
NO_IMPORT_ID = pragma_checker.NO_IMPORT_RULE[0]
NOT_ALONE_ID = pragma_checker.NOT_ALONE_RULE[0]


def check(source):
    handle = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    try:
        handle.write(source)
        handle.close()
        return [(d["rule_id"], d["line"]) for d in checkall.check_file(handle.name)]
    finally:
        os.remove(handle.name)


class AllowModulePragmaTests(unittest.TestCase):
    def test_valid_pragma_allows_module(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "h = hashlib.md5()\n"
        ), [])

    def test_indented_pragma_inside_try(self):
        self.assertEqual(check(
            "try:\n"
            "    #portapy_pragma ALLOW_MODULE\n"
            "    import hashlib\n"
            "    new = hashlib.md5\n"
            "except ImportError:\n"
            "    #portapy_pragma ALLOW_MODULE\n"
            "    import md5\n"
            "    new = md5.new\n"
        ), [])

    def test_without_pragma_still_flagged(self):
        self.assertEqual(check("import hashlib\n"), [(IMPORT_ID, 1)])

    def test_pragma_allows_only_its_own_module(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "import md5\n"
        ), [(IMPORT_ID, 3)])

    def test_allowance_covers_rest_of_file(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "import hashlib\n"
        ), [])

    def test_allowance_does_not_leak_to_next_file(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\nimport hashlib\n"
        ), [])
        self.assertEqual(check("import hashlib\n"), [(IMPORT_ID, 1)])

    def test_blank_line_between_is_rejected(self):
        self.assertEqual(sorted(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "\n"
            "import hashlib\n"
        )), sorted([(IMPORT_ID, 3), (NO_IMPORT_ID, 1)]))

    def test_unsupported_import_forms_are_rejected(self):
        for line in (
            "from hashlib import md5",
            "import hashlib as h",
            "import hashlib, md5",
            "import xml.dom",
            "import hashlib  # comment",
            "import hashlib; x = 1",
        ):
            found = check("#portapy_pragma ALLOW_MODULE\n%s\n" % line)
            self.assertIn((NO_IMPORT_ID, 1), found, line)
            self.assertIn((IMPORT_ID, 2), found, line)

    def test_pragma_at_end_of_file(self):
        self.assertEqual(check("x = 1\n#portapy_pragma ALLOW_MODULE\n"),
                         [(NO_IMPORT_ID, 2)])

    def test_unknown_pragma_is_reported(self):
        self.assertEqual(sorted(check(
            "#portapy_pragma ALLOW_MODULES\n"
            "import hashlib\n"
        )), sorted([(IMPORT_ID, 2), (UNKNOWN_ID, 1)]))

    def test_trailing_pragma_is_reported(self):
        self.assertEqual(sorted(check(
            "import hashlib  #portapy_pragma ALLOW_MODULE\n"
        )), sorted([(IMPORT_ID, 1), (NOT_ALONE_ID, 1)]))

    def test_pragma_inside_string_is_ignored(self):
        self.assertEqual(check(
            "s = '''\n"
            "#portapy_pragma ALLOW_MODULE\n"
            "'''\n"
            "import hashlib\n"
        ), [(IMPORT_ID, 4)])



class AllowModuleEndPragmaTests(unittest.TestCase):
    def test_use_inside_range_is_allowed(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "new = hashlib.md5\n"
            "#portapy_pragma ALLOW_MODULE_END hashlib\n"
            "h = new()\n"
        ), [])

    def test_use_after_end_is_reported(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "#portapy_pragma ALLOW_MODULE_END hashlib\n"
            "h = hashlib.md5()\n"
        ), [(OUT_OF_RANGE_ID, 4)])

    def test_use_before_pragma_is_reported(self):
        self.assertEqual(check(
            "x = hashlib\n"
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
        ), [(OUT_OF_RANGE_ID, 1)])

    def test_import_after_end_is_reported(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "#portapy_pragma ALLOW_MODULE_END hashlib\n"
            "import hashlib\n"
        ), [(IMPORT_ID, 4)])

    def test_reopen_after_end(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "#portapy_pragma ALLOW_MODULE_END hashlib\n"
            "x = 1\n"
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "h = hashlib.md5()\n"
        ), [])

    def test_end_only_closes_its_own_module(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "#portapy_pragma ALLOW_MODULE\n"
            "import binascii\n"
            "#portapy_pragma ALLOW_MODULE_END hashlib\n"
            "x = binascii.hexlify\n"
            "y = hashlib.md5\n"
        ), [(OUT_OF_RANGE_ID, 7)])

    def test_end_without_start_is_reported(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE_END hashlib\n"
        ), [(END_WITHOUT_START_ID, 1)])

    def test_double_end_is_reported(self):
        self.assertEqual(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "#portapy_pragma ALLOW_MODULE_END hashlib\n"
            "#portapy_pragma ALLOW_MODULE_END hashlib\n"
        ), [(END_WITHOUT_START_ID, 4)])

    def test_end_without_module_name_is_unknown(self):
        self.assertEqual(sorted(check(
            "#portapy_pragma ALLOW_MODULE\n"
            "import hashlib\n"
            "#portapy_pragma ALLOW_MODULE_END\n"
        )), [(UNKNOWN_ID, 3)])

    def test_try_except_fallback_with_ends(self):
        self.assertEqual(check(
            "try:\n"
            "    #portapy_pragma ALLOW_MODULE\n"
            "    import hashlib\n"
            "    new = hashlib.md5\n"
            "    #portapy_pragma ALLOW_MODULE_END hashlib\n"
            "except ImportError:\n"
            "    #portapy_pragma ALLOW_MODULE\n"
            "    import md5\n"
            "    new = md5.new\n"
            "    #portapy_pragma ALLOW_MODULE_END md5\n"
            "h = new()\n"
        ), [])


if __name__ == "__main__":
    unittest.main()
