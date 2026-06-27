"""
These tests use a synthetic fixture (not a real ROM).
The fixture's table is placed at file offset 0, so we use a subclassed
driver with POINTER_BASE=0 and offset=0 to avoid needing a full ROM.
"""

from pathlib import Path

import pytest

from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import TableDef
from binforge.drivers.gba.fe7 import FE7Driver


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
    assert rows[0].name_ptr == 0x0847A820


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
