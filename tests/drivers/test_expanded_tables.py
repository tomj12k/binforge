import struct as _struct
from pathlib import Path
from binforge.core.engine import BinaryBuffer


def _make_buf(size: int = 0x900000) -> BinaryBuffer:
    buf = BinaryBuffer.__new__(BinaryBuffer)
    buf._path = Path("test.rom")
    buf._shadow = bytearray(size)
    return buf


def test_fe7_has_skills_table() -> None:
    from binforge.drivers.gba.fe7 import FE7Driver
    buf = _make_buf()
    drv = FE7Driver(buf)
    assert "skills" in drv.table_names()


def test_fe7_parse_skills_returns_64_rows() -> None:
    from binforge.drivers.gba.fe7 import FE7Driver
    buf = _make_buf()
    # Write a skill at row 0: id=5, effect=3, type=1
    file_off = 0x0803F784 - 0x08000000
    buf._shadow[file_off] = 5
    buf._shadow[file_off + 1] = 3
    buf._shadow[file_off + 2] = 1
    drv = FE7Driver(buf)
    rows = drv.parse_table("skills")
    assert len(rows) == 64
    assert rows[0].id == 5
    assert rows[0].effect == 3
    assert rows[0].type == 1


def test_fe7_has_chapters_table() -> None:
    from binforge.drivers.gba.fe7 import FE7Driver
    buf = _make_buf()
    drv = FE7Driver(buf)
    assert "chapters" in drv.table_names()


def test_fe7_parse_chapters_returns_47_rows() -> None:
    from binforge.drivers.gba.fe7 import FE7Driver
    buf = _make_buf()
    file_off = 0x08068B30 - 0x08000000
    buf._shadow[file_off] = 7      # id
    buf._shadow[file_off + 1] = 12  # map_id
    buf._shadow[file_off + 2] = 2   # music
    drv = FE7Driver(buf)
    rows = drv.parse_table("chapters")
    assert len(rows) == 47
    assert rows[0].id == 7


def test_fe8_has_skills_and_chapters() -> None:
    from binforge.drivers.gba.fe8 import FE8Driver
    buf = _make_buf()
    drv = FE8Driver(buf)
    assert "skills" in drv.table_names()
    assert "chapters" in drv.table_names()


def test_fe8_parse_chapters_returns_46_rows() -> None:
    from binforge.drivers.gba.fe8 import FE8Driver
    buf = _make_buf()
    drv = FE8Driver(buf)
    rows = drv.parse_table("chapters")
    assert len(rows) == 46


def test_fe6_has_items_table() -> None:
    from binforge.drivers.gba.fe6 import FE6Driver
    buf = _make_buf()
    drv = FE6Driver(buf)
    assert "items" in drv.table_names()


def test_fe6_parse_items_returns_213_rows() -> None:
    from binforge.drivers.gba.fe6 import FE6Driver
    buf = _make_buf()
    file_off = 0x08040A28 - 0x08000000
    buf._shadow[file_off + 4] = 2   # type
    buf._shadow[file_off + 5] = 45  # uses
    drv = FE6Driver(buf)
    rows = drv.parse_table("items")
    assert len(rows) == 213
    assert rows[0].type == 2
    assert rows[0].uses == 45


def test_fe4_has_classes_table() -> None:
    from binforge.drivers.snes.fe4 import FE4Driver
    buf = _make_buf()
    drv = FE4Driver(buf)
    assert "classes" in drv.table_names()


def test_fe4_parse_classes_returns_64_rows() -> None:
    from binforge.drivers.snes.fe4 import FE4Driver
    buf = _make_buf()
    buf._shadow[0x025E80] = 3   # id
    buf._shadow[0x025E81] = 6   # move
    buf._shadow[0x025E82] = 10  # con
    drv = FE4Driver(buf)
    rows = drv.parse_table("classes")
    assert len(rows) == 64
    assert rows[0].id == 3
    assert rows[0].move == 6
    assert rows[0].con == 10
