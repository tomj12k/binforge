import struct
import pytest
from pathlib import Path

from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, u8, u16, u32, ptr
from binforge.drivers.base import FormatDriver
from binforge.errors import TableNotFoundError


class _TestDriver(FormatDriver):
    """Minimal driver with pointer base 0 so offsets == file offsets."""
    MAGIC = b"\xFE\xFE"
    ENDIAN = "little"
    POINTER_BASE = 0x00000000

    def detect(self, buf: BinaryBuffer) -> bool:
        return buf.read_u16(0) == 0xFEFE

    def tables(self) -> dict[str, TableDef]:
        return {
            "units": TableDef(
                offset=0x00000000,  # file offset 0
                row_size=8,
                count=2,
                fields=[
                    Field("hp",  u8,  0x00),
                    Field("str", u8,  0x01),
                    Field("spd", u8,  0x02),
                    Field("lck", u8,  0x03),
                    Field("exp", u16, 0x04),
                    Field("id",  u16, 0x06),
                ],
            )
        }


def _make_driver(rows: list[tuple[int, ...]]) -> tuple[_TestDriver, Path]:
    """Build a synthetic file with `rows` of (hp, str, spd, lck, exp, id)."""
    import tempfile, os
    data = bytearray()
    for hp, s, spd, lck, exp, uid in rows:
        data += struct.pack("<BBBBHH", hp, s, spd, lck, exp, uid)
    p = Path(tempfile.mktemp(suffix=".bin"))
    p.write_bytes(bytes(data))
    buf = BinaryBuffer(p)
    return _TestDriver(buf), p


def test_parse_table_reads_fields():
    drv, p = _make_driver([(20, 4, 5, 3, 100, 1), (18, 6, 7, 2, 50, 2)])
    rows = drv.parse_table("units")
    assert len(rows) == 2
    assert rows[0].hp == 20
    assert rows[0].str == 4
    assert rows[0].exp == 100
    assert rows[1].id == 2
    p.unlink()


def test_parse_table_not_found():
    drv, p = _make_driver([(1, 2, 3, 4, 5, 6)])
    with pytest.raises(TableNotFoundError):
        drv.parse_table("nonexistent")
    p.unlink()


def test_pack_table_writes_back(tmp_path):
    drv, p = _make_driver([(20, 4, 5, 3, 100, 1), (1, 2, 3, 4, 5, 6)])
    rows = drv.parse_table("units")
    rows[0].hp = 99
    rows[0].exp = 9999
    drv.pack_table("units", rows)
    drv.commit(tmp_path / "out.bin")

    out = BinaryBuffer(tmp_path / "out.bin")
    assert out.read_u8(0x00) == 99
    assert out.read_u16(0x04) == 9999
    p.unlink()


def test_table_names():
    drv, p = _make_driver([(1, 2, 3, 4, 5, 6)])
    assert drv.table_names() == ["units"]
    p.unlink()
