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
