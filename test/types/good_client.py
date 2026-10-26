"""Well-typed, Python 2.0-compatible use of the Ppy tags. mypy must report nothing.

Also passes portapy: type comments are comments, and every tag is reached
through 'ppy.', so no typing import is needed.
"""

import portapy_sdk as ppy


def make_entry(path_hex, length):
    # type: (ppy.PpyAsciiBytes, int) -> ppy.PpyBDict
    e = {}  # type: ppy.PpyBDict
    ppy.bd_add(e, 'hexl_path', [path_hex])
    ppy.bd_add(e, 'length', length)
    return e


def marshall(entries):
    # type: (ppy.PpyList[ppy.PpyBDict]) -> ppy.PpyBencoded
    body = {}  # type: ppy.PpyBDict
    ppy.bd_add(body, 'name_kind', ppy.a2b('native-bytes'))
    values = []  # type: ppy.PpyBList
    for e in entries:
        values.append(e)
    ppy.bd_add(body, 'entries', values)
    return ppy.bencode(body)


def read_offsets(http_body):
    # type: (ppy.PpyBytes) -> ppy.PpyList[int]
    # An HTTP body is plain bytes: mark it as bencoded at the boundary, then read it with checked readers.
    reply = ppy.bv_dict(ppy.bdecode(ppy.PpyBencoded(http_body)))
    offsets = []  # type: ppy.PpyList[int]
    for w in ppy.bd_get_list(reply, 'entries'):
        offsets.append(ppy.bd_get_int(ppy.bv_dict(w), 'offset'))
    return offsets


def name_kind_of(reply):
    # type: (ppy.PpyBDict) -> ppy.PpyAsciiStr
    return ppy.b2a(ppy.bd_get_bytes(reply, 'name_kind'))


def make_reply(offset):
    # type: (int) -> ppy.PpyBencoded
    w = {}  # type: ppy.PpyBDict
    ppy.bd_add(w, 'hexl_path', [ppy.a2b('2f746d70')])
    ppy.bd_add(w, 'offset', offset)
    reply = {}  # type: ppy.PpyBDict
    ppy.bd_add(reply, 'entries', [w])
    return ppy.bencode(reply)


def first_or_none(values, describe):
    # type: (ppy.PpyList[ppy.PpyTuple[ppy.PpyAsciiStr, int]], ppy.PpyCallable[[int], ppy.PpyAsciiStr]) -> ppy.PpyOptional[ppy.PpyUnion2[ppy.PpyAsciiStr, int]]
    """Uses each generic helper, so the SDK's generic aliases stay valid."""
    if len(values) == 0:
        return None
    name, count = values[0]
    if count < 0:
        return describe(count)
    return name


def describe_count(n):
    # type: (int) -> ppy.PpyAsciiStr
    return 'count %d' % n


def main():
    # type: () -> None
    manifest = marshall([make_entry(ppy.a2b('2f746d70'), 3)])
    offsets = read_offsets(make_reply(7))
    ppy.prnt(len(manifest) > 0, offsets, first_or_none([('a', 1)], describe_count))


if __name__ == '__main__':
    main()
