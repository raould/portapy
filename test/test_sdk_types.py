"""Tests for the Ppy type tags: the runtime side, mypy on the SDK itself, and mypy on two sample clients.

The mypy checks are skipped when mypy is not installed.
"""

import os
import re
import shutil
import subprocess
import sys
import unittest

PORTAPY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PORTAPY_DIR, "src")
TYPES_DIR = os.path.join(os.path.dirname(__file__), "types")
SCRIPT_DIR = os.path.join(PORTAPY_DIR, "scripts")
for path in (SRC_DIR, SCRIPT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import portapy_sdk as ppy  # noqa: E402
import checkall  # noqa: E402


def run_tool(tool, args):
    env = dict(os.environ)
    env["MYPYPATH"] = SRC_DIR
    env["PYTHONPATH"] = SRC_DIR
    return subprocess.run([tool] + args, cwd=SRC_DIR, env=env, capture_output=True, text=True)


class RuntimeTagTests(unittest.TestCase):
    def test_source_tags_are_the_real_types(self):
        self.assertIs(ppy.PpyNativeStr, str)
        self.assertIs(ppy.PpyAsciiStr, str)
        self.assertIs(ppy.PpyBytes, bytes)
        self.assertIs(ppy.PpyText, str)

    def test_ascii_bytes_constructor_checks(self):
        self.assertEqual(ppy.PpyAsciiBytes(b"abc"), b"abc")
        self.assertRaises(ValueError, ppy.PpyAsciiBytes, b"caf\xe9")
        self.assertRaises(TypeError, ppy.PpyAsciiBytes, "abc")
        self.assertEqual(ppy.PpyBKey(b"length"), b"length")

    def test_bencoded_constructor_checks_type(self):
        self.assertEqual(ppy.PpyBencoded(b"i1e"), b"i1e")
        self.assertRaises(TypeError, ppy.PpyBencoded, "i1e")

    def test_checked_readers(self):
        reply = ppy.bv_dict(ppy.bdecode(ppy.PpyBencoded(b"d7:entriesld6:offseti7eeee")))
        entries = ppy.bd_get_list(reply, "entries")
        self.assertEqual(ppy.bd_get_int(ppy.bv_dict(entries[0]), "offset"), 7)
        self.assertRaises(TypeError, ppy.bd_get_bytes, reply, "entries")
        self.assertRaises(TypeError, ppy.bv_int, b"7")
        self.assertRaises(TypeError, ppy.bv_dict, [])
        self.assertRaises(KeyError, ppy.bd_get_int, reply, "missing")


class PortabilityTests(unittest.TestCase):
    def test_samples_pass_portapy(self):
        for name in ("good_client.py", "bad_client.py"):
            path = os.path.join(TYPES_DIR, name)
            self.assertEqual(checkall.check_file(path), [], name)


@unittest.skipIf(shutil.which("mypy") is None, "mypy not installed")
class MypyTests(unittest.TestCase):
    def test_sdk_itself_is_clean(self):
        r = run_tool("mypy", ["--strict", os.path.join(SRC_DIR, "portapy_sdk", "__init__.py")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_good_client_is_clean(self):
        r = run_tool("mypy", ["--strict", os.path.join(TYPES_DIR, "good_client.py")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bad_client_errors_exactly_where_marked(self):
        path = os.path.join(TYPES_DIR, "bad_client.py")
        expected = set()
        handle = open(path)
        try:
            for number, line in enumerate(handle, 1):
                if "# EXPECT-ERROR" in line:
                    expected.add(number)
        finally:
            handle.close()
        r = run_tool("mypy", ["--strict", path])
        found = set(int(m.group(1)) for m in re.finditer(r"bad_client\.py:(\d+): error:", r.stdout))
        self.assertEqual(found, expected, r.stdout)


if __name__ == "__main__":
    unittest.main()
