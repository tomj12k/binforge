"""
These tests use a synthetic fixture (not a real ROM).
The fixture's table is placed at file offset 0, so we use a subclassed
driver with POINTER_BASE=0 and offset=0 to avoid needing a full ROM.
"""

import struct as _struct
from pathlib import Path

import pytest

from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import TableDef
from binforge.drivers.gba.fe7 import FE7Driver
from binforge.errors import PatchSizeError


class _FixtureDriver(FE7Driver):
    """Override table offset to 0x00000000 so file offset == ROM offset."""

    POINTER_BASE = 0x00000000

    def tables(self) -> dict[str, TableDef]:
        base = super().tables()
        chars = base["characters"]
        return {
            "characters": TableDef(
                offset=0x00000000,  # fixture starts at byte 0
                row_size=chars.row_size,
                count=3,  # fixture has 3 rows
                fields=chars.fields,
            )
        }


FIXTURE = Path(__file__).parent.parent / "fixtures" / "fe7_chars.bin"


@pytest.fixture()
def drv() -> _FixtureDriver:
    return _FixtureDriver(BinaryBuffer(FIXTURE))


def test_parse_character_hp(drv: _FixtureDriver) -> None:
    rows = drv.parse_table("characters")
    assert rows[0].hp == 20  # Lyn
    assert rows[1].hp == 16  # Eliwood
    assert rows[2].hp == 23  # Hector


def test_parse_character_name_ptr(drv: _FixtureDriver) -> None:
    rows = drv.parse_table("characters")
    # name_ptr is now a str_ptr field; raw pointer is preserved in _raw
    assert rows[0]._raw.get("name_ptr") == 0x0847A820


def test_pack_modifies_hp(drv: _FixtureDriver, tmp_path: Path) -> None:
    rows = drv.parse_table("characters")
    rows[0].hp = 99
    drv.pack_table("characters", rows)
    drv.commit(tmp_path / "out.bin")

    result_drv = _FixtureDriver(BinaryBuffer(tmp_path / "out.bin"))
    updated = result_drv.parse_table("characters")
    assert updated[0].hp == 99
    assert updated[1].hp == 16  # unchanged


def test_three_rows_parsed(drv: _FixtureDriver) -> None:
    rows = drv.parse_table("characters")
    assert len(rows) == 3


def test_detect_with_valid_game_code(tmp_path: Path) -> None:
    """Test that detect() returns True for buffer with AFEE at offset 0xAC."""
    buf_data = bytearray(0xB0)  # At least 0xB0 bytes
    buf_data[0xAC:0xB0] = b"AFEE"
    tmp_file = tmp_path / "test_rom.gba"
    tmp_file.write_bytes(buf_data)

    drv = FE7Driver(BinaryBuffer(tmp_file))
    assert drv.detect(BinaryBuffer(tmp_file)) is True


def test_detect_with_invalid_game_code(tmp_path: Path) -> None:
    """Test that detect() returns False for buffer without AFEE at offset 0xAC."""
    buf_data = bytearray(0xB0)  # At least 0xB0 bytes
    buf_data[0xAC:0xB0] = b"XXXX"  # Wrong code
    tmp_file = tmp_path / "test_rom.gba"
    tmp_file.write_bytes(buf_data)

    drv = FE7Driver(BinaryBuffer(tmp_file))
    assert drv.detect(BinaryBuffer(tmp_file)) is False


def test_pack_table_overflow_raises(drv: _FixtureDriver) -> None:
    """Passing more rows than tdef.count must raise PatchSizeError."""
    rows = drv.parse_table("characters")
    tdef = drv.tables()["characters"]
    # Duplicate last row to exceed declared count
    extra_rows = rows + [rows[-1]] * (tdef.count - len(rows) + 1)
    with pytest.raises(PatchSizeError):
        drv.pack_table("characters", extra_rows)


# ── str_ptr / TEXT_CODEC integration tests ──────────────────────────────────


def _make_fe7_str_buf() -> object:
    """Return a BinaryBuffer-like with a FE7 ROM layout containing name pointers."""
    from pathlib import Path

    from binforge.core.engine import BinaryBuffer
    from binforge.drivers.gba.codec_fe7 import FE7_CODEC

    # Build a minimal ROM with:
    # - character table at 0x3D6C0 (file offset = 0x0803D6C0 - 0x08000000)
    # - name "Lyn" encoded at file offset 0x3A000, pointed to by ROM addr 0x0803A000
    rom = bytearray(0x70000)
    name_file_off = 0x3A000
    name_rom_addr = 0x08000000 + name_file_off
    encoded = FE7_CODEC.encode("Lyn")
    rom[name_file_off : name_file_off + len(encoded)] = encoded
    # character row 0 at file offset 0x3D6C0: name_ptr at offset 0x00
    char_file_off = 0x3D6C0
    _struct.pack_into("<I", rom, char_file_off, name_rom_addr)
    rom[char_file_off + 0x04] = 20  # hp

    buf = BinaryBuffer.__new__(BinaryBuffer)
    buf._path = Path("fe7_str_test.gba")
    buf._shadow = bytearray(rom)
    return buf


def test_fe7_name_ptr_resolves_to_string() -> None:
    from binforge.drivers.gba.fe7 import FE7Driver

    buf = _make_fe7_str_buf()
    drv = FE7Driver(buf)
    rows = drv.parse_table("characters")
    assert isinstance(rows[0].name_ptr, str)
    assert rows[0].name_ptr == "Lyn"


def test_fe7_name_ptr_raw_preserved() -> None:
    from binforge.drivers.gba.fe7 import FE7Driver

    buf = _make_fe7_str_buf()
    drv = FE7Driver(buf)
    rows = drv.parse_table("characters")
    assert rows[0]._raw.get("name_ptr") == 0x0803A000


def test_fe7_pack_table_reencodes_name() -> None:
    from binforge.drivers.gba.codec_fe7 import FE7_CODEC  # noqa: F401
    from binforge.drivers.gba.fe7 import FE7Driver

    buf = _make_fe7_str_buf()
    drv = FE7Driver(buf)
    rows = drv.parse_table("characters")
    rows[0].name_ptr = "Lyn"  # same 3-char name — same encoded length
    drv.pack_table("characters", rows)
    drv2 = FE7Driver(buf)
    rows2 = drv2.parse_table("characters")
    assert rows2[0].name_ptr == "Lyn"
