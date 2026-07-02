import pytest
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


def _make_fe13_buf_with_jobs() -> BinaryBuffer:
    """Build a minimal FE13 ROMFS with both Person.bin.lz and JobData.bin.lz."""
    from binforge.core.compression import compress_lz11
    from binforge.drivers.n3ds.romfs_builder import RomFSBuilder

    person_raw = bytearray(108 * 85)  # FE13 person size
    job_raw = bytearray(96 * 66)      # FE13 class size
    job_raw[0x00] = 7   # id
    job_raw[0x08] = 5   # move

    files = {
        "GameData/Person.bin.lz": compress_lz11(bytes(person_raw)),
        "GameData/JobData.bin.lz": compress_lz11(bytes(job_raw)),
    }
    blob = RomFSBuilder().build(files)
    buf = BinaryBuffer.__new__(BinaryBuffer)
    buf._path = Path("fe13_jobs.romfs")
    buf._shadow = bytearray(blob)
    return buf


def test_fe13_has_classes_table() -> None:
    from binforge.drivers.n3ds.fe13 import FE13Driver
    buf = _make_fe13_buf_with_jobs()
    drv = FE13Driver(buf)
    assert "classes" in drv.table_names()


def test_fe13_parse_classes() -> None:
    from binforge.drivers.n3ds.fe13 import FE13Driver
    buf = _make_fe13_buf_with_jobs()
    drv = FE13Driver(buf)
    rows = drv.parse_table("classes")
    assert len(rows) == 66
    assert rows[0].id == 7
    assert rows[0].move == 5


def test_fe13_pack_classes_routes_to_jobdata() -> None:
    """pack_table("classes") must edit JobData.bin and leave Person.bin untouched."""
    from binforge.drivers.n3ds.fe13 import FE13Driver

    buf = _make_fe13_buf_with_jobs()
    drv = FE13Driver(buf)
    chars_before = drv.parse_table("characters")
    rows = drv.parse_table("classes")
    rows[0].move = 9
    drv.pack_table("classes", rows)

    drv2 = FE13Driver(buf)
    classes_after = drv2.parse_table("classes")
    assert classes_after[0].move == 9
    assert classes_after[0].id == 7
    chars_after = drv2.parse_table("characters")
    for before, after in zip(chars_before, chars_after, strict=True):
        assert before.hp == after.hp
        assert before.name_hash == after.name_hash


def test_fe13_pack_unknown_table_raises() -> None:
    from binforge.drivers.n3ds.fe13 import FE13Driver
    from binforge.errors import TableNotFoundError

    buf = _make_fe13_buf_with_jobs()
    drv = FE13Driver(buf)
    with pytest.raises(TableNotFoundError):
        drv.pack_table("nonexistent", [])
