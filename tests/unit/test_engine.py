import pytest
from pathlib import Path
from binforge.core.engine import BinaryBuffer
from binforge.errors import PatchSizeError, CommitError


def _buf(data: bytes) -> BinaryBuffer:
    """Construct a BinaryBuffer from raw bytes without touching disk."""
    b = object.__new__(BinaryBuffer)
    b._path = Path("synthetic.bin")
    b._shadow = bytearray(data)
    return b


def test_len():
    assert len(_buf(b"\x00\x01\x02")) == 3


def test_read_u8():
    b = _buf(b"\x0a\x0b\x0c")
    assert b.read_u8(0) == 0x0A
    assert b.read_u8(2) == 0x0C


def test_read_u16_little():
    b = _buf(b"\x01\x02\x00\x00")
    assert b.read_u16(0) == 0x0201


def test_read_u16_big():
    b = _buf(b"\x01\x02\x00\x00")
    assert b.read_u16(0, big=True) == 0x0102


def test_read_u32_little():
    # GBA pointer 0x0803A820 stored little-endian
    b = _buf(bytes([0x20, 0xA8, 0x03, 0x08]))
    assert b.read_u32(0) == 0x0803A820


def test_read_u32_big():
    b = _buf(bytes([0x08, 0x03, 0xA8, 0x20]))
    assert b.read_u32(0, big=True) == 0x0803A820


def test_read_i8_negative():
    b = _buf(bytes([0xFF]))
    assert b.read_i8(0) == -1


def test_read_bytes():
    b = _buf(b"\xde\xad\xbe\xef")
    assert b.read_bytes(1, 2) == b"\xad\xbe"


def test_patch_success():
    b = _buf(b"\x00\x00\x00\x00")
    b.patch(1, b"\xff\xee")
    assert bytes(b._shadow) == b"\x00\xff\xee\x00"


def test_patch_at_end():
    b = _buf(b"\x00\x00")
    b.patch(1, b"\xff")
    assert bytes(b._shadow) == b"\x00\xff"


def test_patch_size_error_overflow():
    b = _buf(b"\x00\x00")
    with pytest.raises(PatchSizeError):
        b.patch(1, b"\xff\xff")  # offset 1 + 2 bytes = 3 > file size 2


def test_patch_does_not_touch_disk(tmp_path):
    p = tmp_path / "src.bin"
    p.write_bytes(b"\x01\x02\x03")
    buf = BinaryBuffer(p)
    buf.patch(0, b"\xff")
    assert p.read_bytes() == b"\x01\x02\x03"  # original untouched


def test_commit_to_new_path(tmp_path):
    src = tmp_path / "src.bin"
    dst = tmp_path / "dst.bin"
    src.write_bytes(b"\x01\x02\x03")
    buf = BinaryBuffer(src)
    buf.patch(0, b"\xff")
    buf.commit(dst)
    assert dst.read_bytes() == b"\xff\x02\x03"
    assert src.read_bytes() == b"\x01\x02\x03"


def test_commit_in_place(tmp_path):
    p = tmp_path / "file.bin"
    p.write_bytes(b"\x00\x00")
    buf = BinaryBuffer(p)
    buf.patch(0, b"\xab")
    buf.commit(in_place=True)
    assert p.read_bytes() == b"\xab\x00"


def test_commit_requires_path_or_in_place(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"\x00")
    buf = BinaryBuffer(p)
    with pytest.raises(CommitError):
        buf.commit()


# ── exploration API ──────────────────────────────────────────────────────────


def test_from_bytes_round_trip():
    buf = BinaryBuffer.from_bytes(b"\x01\x02\x03\x04")
    assert bytes(buf) == b"\x01\x02\x03\x04"
    assert len(buf) == 4
    buf.patch(1, b"\xff")
    assert bytes(buf) == b"\x01\xff\x03\x04"


def test_from_bytes_commit_without_path_raises():
    buf = BinaryBuffer.from_bytes(b"\x00")
    with pytest.raises(CommitError):
        buf.commit()
    with pytest.raises(CommitError):
        buf.commit(in_place=True)


def test_from_bytes_commit_to_explicit_path(tmp_path):
    dst = tmp_path / "out.bin"
    buf = BinaryBuffer.from_bytes(b"\xaa\xbb")
    buf.commit(dst)
    assert dst.read_bytes() == b"\xaa\xbb"


def test_bytes_and_len_on_file_buffer(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"\x10\x20\x30")
    buf = BinaryBuffer(p)
    assert bytes(buf) == b"\x10\x20\x30"
    assert len(buf) == 3


def test_read_cstring_normal():
    buf = BinaryBuffer.from_bytes(b"abc\x00def\x00")
    assert buf.read_cstring(0) == b"abc"
    assert buf.read_cstring(4) == b"def"


def test_read_cstring_no_terminator_stops_at_end():
    buf = BinaryBuffer.from_bytes(b"hello")
    assert buf.read_cstring(0) == b"hello"


def test_read_cstring_at_end_and_max_len():
    buf = BinaryBuffer.from_bytes(b"abcdef")
    assert buf.read_cstring(6) == b""
    assert buf.read_cstring(0, max_len=3) == b"abc"


def test_hexdump_exact_format():
    buf = BinaryBuffer.from_bytes(bytes(range(0x41, 0x41 + 20)))  # 'A'..'T'
    expected = (
        "00000000  41 42 43 44 45 46 47 48  49 4a 4b 4c 4d 4e 4f 50  |ABCDEFGHIJKLMNOP|\n"
        "00000010  51 52 53 54                                       |QRST|"
    )
    assert buf.hexdump() == expected


def test_hexdump_offset_and_clamp():
    buf = BinaryBuffer.from_bytes(b"\x00" * 4 + b"\x7f\x80")
    out = buf.hexdump(offset=4, length=100)
    assert out == "00000004  7f 80                                             |..|"


def test_hexdump_empty_region():
    buf = BinaryBuffer.from_bytes(b"\x01")
    assert buf.hexdump(offset=1) == ""


def test_find_bytes_needle():
    buf = BinaryBuffer.from_bytes(b"\x00\xaf\xee\x00\xaf\xee")
    assert buf.find(b"\xaf\xee") == [1, 4]


def test_find_hex_string_needle():
    buf = BinaryBuffer.from_bytes(b"\x00\xaf\xee\x00\xaf\xee\x00")
    assert buf.find("AF EE 00") == [1, 4]
    assert buf.find("afee00") == [1, 4]


def test_find_start_and_limit():
    buf = BinaryBuffer.from_bytes(b"\xaa" * 10)
    assert buf.find(b"\xaa", start=8) == [8, 9]
    assert buf.find(b"\xaa", limit=3) == [0, 1, 2]


def test_find_no_matches():
    buf = BinaryBuffer.from_bytes(b"\x01\x02\x03")
    assert buf.find(b"\xff") == []


def test_dirty_ranges_no_edits():
    buf = BinaryBuffer.from_bytes(b"\x00" * 32)
    assert buf.dirty_ranges() == []


def test_dirty_ranges_single_patch():
    buf = BinaryBuffer.from_bytes(b"\x00" * 32)
    buf.patch(10, b"\x01\x02\x03")
    assert buf.dirty_ranges() == [(10, 3)]


def test_dirty_ranges_nearby_patches_merge():
    buf = BinaryBuffer.from_bytes(b"\x00" * 32)
    buf.patch(4, b"\x01\x01")
    buf.patch(10, b"\x02")  # gap of 4 from end of first span -> merge
    assert buf.dirty_ranges() == [(4, 7)]


def test_dirty_ranges_far_apart_stay_separate():
    buf = BinaryBuffer.from_bytes(b"\x00" * 64)
    buf.patch(0, b"\x01")
    buf.patch(40, b"\x02\x02")
    assert buf.dirty_ranges() == [(0, 1), (40, 2)]


def test_dirty_ranges_patch_to_same_value_is_clean():
    buf = BinaryBuffer.from_bytes(b"\x05\x06")
    buf.patch(0, b"\x05")
    assert buf.dirty_ranges() == []


def test_dirty_ranges_length_change_reports_all_dirty():
    buf = BinaryBuffer.from_bytes(b"\x00" * 8)
    buf.replace_contents(b"\x00" * 16)
    assert buf.dirty_ranges() == [(0, 16)]


def test_replace_contents_swaps_shadow():
    buf = BinaryBuffer.from_bytes(b"\x01\x02")
    buf.replace_contents(b"\xaa\xbb\xcc")
    assert bytes(buf) == b"\xaa\xbb\xcc"
    assert len(buf) == 3
