"""Mistakes the Ppy tags exist to catch. mypy must report an error on every line marked EXPECT-ERROR, and nowhere else."""

import portapy_sdk as ppy


def needs_ascii_bytes(b):
    # type: (ppy.PpyAsciiBytes) -> None
    pass


def wrong_conversions(raw, text):
    # type: (ppy.PpyBytes, ppy.PpyAsciiStr) -> None
    needs_ascii_bytes(raw)                    # EXPECT-ERROR plain bytes are not PpyAsciiBytes
    needs_ascii_bytes(ppy.PpyAsciiBytes(raw))
    ppy.bdecode(raw)                          # EXPECT-ERROR plain bytes are not PpyBencoded
    ppy.bdecode(ppy.PpyBencoded(raw))
    ppy.a2b(raw)                              # EXPECT-ERROR a2b takes a str literal, not bytes
    ppy.b2a(text)                             # EXPECT-ERROR b2a takes bytes, not a str
    needs_ascii_bytes(ppy.a2b(text))


def unchecked_reply(body):
    # type: (ppy.PpyBencoded) -> int
    reply = ppy.bdecode(body)
    return reply[ppy.bkey('offset')]          # EXPECT-ERROR a decoded value must go through bv_dict/bd_get_* first
