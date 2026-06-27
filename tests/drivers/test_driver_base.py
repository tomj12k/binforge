import struct
import struct as _struct
import pytest
from pathlib import Path

from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, u8, u16, str_ptr
from binforge.core.text import TextCodec
from binforge.drivers.base import FormatDriver
from binforge.errors import TableNotFoundError
from binforge.registry import register


class _TestDriver(FormatDriver):
    """Minimal driver with pointer base 0 so offsets == file offsets."""

    MAGIC = b"\xfe\xfe"
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
                    Field("hp", u8, 0x00),
                    Field("str", u8, 0x01),
                    Field("spd", u8, 0x02),
                    Field("lck", u8, 0x03),
                    Field("exp", u16, 0x04),
                    Field("id", u16, 0x06),
                ],
            )
        }


def _make_driver(rows: list[tuple[int, ...]]) -> tuple[_TestDriver, Path]:
    """Build a synthetic file with `rows` of (hp, str, spd, lck, exp, id)."""
    import tempfile

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


# ── str_ptr tests ────────────────────────────────────────────────────────────

_SIMPLE_TABLE: dict[int, str] = {0x01: "L", 0x02: "y", 0x03: "n"}
_SIMPLE_CODEC = TextCodec(_SIMPLE_TABLE)
_GBA_BASE = 0x08000000


def _make_str_ptr_driver_buf() -> tuple[BinaryBuffer, type[FormatDriver]]:
    """Build a synthetic ROM with a name pointer and encoded string."""
    rom = bytearray(0x400)
    # Write "Lyn\x00" encoded at file offset 0x200 (ROM addr 0x08000200)
    rom[0x200] = 0x01  # L
    rom[0x201] = 0x02  # y
    rom[0x202] = 0x03  # n
    rom[0x203] = 0x00  # null terminator
    # Write pointer to 0x08000200 at table row 0 field 0
    _struct.pack_into("<I", rom, 0x100, 0x08000200)
    # Write hp at offset 0x04
    rom[0x104] = 25

    @register
    class _StrPtrDriver(FormatDriver):
        MAGIC = b""
        ENDIAN = "little"
        POINTER_BASE = _GBA_BASE
        TEXT_CODEC = _SIMPLE_CODEC

        def detect(self, buf: BinaryBuffer) -> bool:
            return True

        def tables(self) -> dict[str, TableDef]:
            return {
                "chars": TableDef(
                    offset=_GBA_BASE + 0x100,
                    row_size=8,
                    count=1,
                    fields=[
                        Field("name_ptr", str_ptr, 0x00),
                        Field("hp", u8, 0x04),
                    ],
                )
            }

    buf = BinaryBuffer.__new__(BinaryBuffer)
    buf._path = Path("test.gba")
    buf._shadow = bytearray(rom)
    return buf, _StrPtrDriver


def test_str_ptr_resolves_to_string() -> None:
    buf, Drv = _make_str_ptr_driver_buf()
    drv = Drv(buf)
    rows = drv.parse_table("chars")
    assert rows[0].name_ptr == "Lyn"
    assert rows[0].hp == 25


def test_str_ptr_raw_preserved() -> None:
    buf, Drv = _make_str_ptr_driver_buf()
    drv = Drv(buf)
    rows = drv.parse_table("chars")
    assert rows[0]._raw.get("name_ptr") == 0x08000200


def test_pack_table_reencodes_string_same_length() -> None:
    buf, Drv = _make_str_ptr_driver_buf()
    drv = Drv(buf)
    rows = drv.parse_table("chars")
    rows[0].name_ptr = "nLy"  # same length (3 chars + null = 4 bytes)
    drv.pack_table("chars", rows)
    drv2 = Drv(buf)
    rows2 = drv2.parse_table("chars")
    assert rows2[0].name_ptr == "nLy"


def test_pack_table_raw_pointer_bypass() -> None:
    buf, Drv = _make_str_ptr_driver_buf()
    drv = Drv(buf)
    rows = drv.parse_table("chars")
    rows[0].name_ptr = 0x08000200  # set as int — bypass codec
    drv.pack_table("chars", rows)
    # pointer field in ROM should still be 0x08000200
    raw_ptr = _struct.unpack_from("<I", buf._shadow, 0x100)[0]
    assert raw_ptr == 0x08000200


def test_str_ptr_raw_preserved_without_text_codec() -> None:
    """Test that _pending_raw is populated for str_ptr fields even when TEXT_CODEC is None."""
    rom = bytearray(0x400)
    # Write pointer to 0x08000200 at table row 0 field 0
    _struct.pack_into("<I", rom, 0x100, 0x08000200)
    # Write hp at offset 0x04
    rom[0x104] = 25

    @register
    class _StrPtrNoCodecDriver(FormatDriver):
        MAGIC = b""
        ENDIAN = "little"
        POINTER_BASE = _GBA_BASE
        TEXT_CODEC = None  # No text codec

        def detect(self, buf: BinaryBuffer) -> bool:
            return True

        def tables(self) -> dict[str, TableDef]:
            return {
                "chars": TableDef(
                    offset=_GBA_BASE + 0x100,
                    row_size=8,
                    count=1,
                    fields=[
                        Field("name_ptr", str_ptr, 0x00),
                        Field("hp", u8, 0x04),
                    ],
                )
            }

    buf = BinaryBuffer.__new__(BinaryBuffer)
    buf._path = Path("test.gba")
    buf._shadow = bytearray(rom)
    drv = _StrPtrNoCodecDriver(buf)
    rows = drv.parse_table("chars")
    # When TEXT_CODEC is None, the field value is the raw pointer
    assert rows[0].name_ptr == 0x08000200
    # _pending_raw should be populated with the raw pointer value
    assert rows[0]._raw.get("name_ptr") == 0x08000200
