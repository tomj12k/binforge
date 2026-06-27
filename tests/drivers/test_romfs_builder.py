from pathlib import Path

import pytest
from binforge.core.compression import compress_lz11
from binforge.core.engine import BinaryBuffer
from binforge.drivers.n3ds.romfs import RomFS
from binforge.drivers.n3ds.romfs_builder import RomFSBuilder
from binforge.errors import RomFSBuildError


def test_duplicate_path_raises() -> None:
    builder = RomFSBuilder()
    # build() with duplicate keys isn't possible via dict, but duplicate
    # path normalisation (e.g. leading slash vs no slash) should raise
    with pytest.raises(RomFSBuildError):
        builder.build({"/foo.bin": b"a", "foo.bin": b"b"})


def _build(files: dict[str, bytes | None]) -> object:
    """Helper: return root _DirNode without serialising."""
    from binforge.drivers.n3ds.romfs_builder import RomFSBuilder
    builder = RomFSBuilder()
    norm = builder._normalise(files)
    return builder._build_tree(norm)


def test_tree_single_file() -> None:
    from binforge.drivers.n3ds.romfs_builder import _DirNode
    root = _build({"foo.bin": b"\x01\x02"})
    assert isinstance(root, _DirNode)
    assert root.name == ""
    assert len(root.files) == 1
    assert root.files[0].name == "foo.bin"
    assert root.files[0].data == b"\x01\x02"


def test_tree_nested_dir() -> None:
    root = _build({"GameData/foo.bin": b"x", "GameData/bar.bin": b"y"})
    assert len(root.children) == 1
    child = root.children[0]
    assert child.name == "GameData"
    assert len(child.files) == 2


def test_tree_delete_omits_file() -> None:
    root = _build({"keep.bin": b"k", "gone.bin": None})
    from binforge.drivers.n3ds.romfs_builder import _DirNode
    assert isinstance(root, _DirNode)
    names = [f.name for f in root.files]
    assert "keep.bin" in names
    assert "gone.bin" not in names


# ── Round-trip tests ─────────────────────────────────────────────────────────


def test_roundtrip_single_file() -> None:
    files = {"hello.bin": b"hello world"}
    blob = RomFSBuilder().build(files)
    romfs = RomFS(blob)
    assert romfs.read_file("hello.bin") == b"hello world"


def test_roundtrip_multiple_files() -> None:
    files = {
        "GameData/Person.bin": b"\x01" * 100,
        "GameData/Job.bin": b"\x02" * 50,
        "root.bin": b"\x03" * 10,
    }
    blob = RomFSBuilder().build(files)
    romfs = RomFS(blob)
    for path, data in files.items():
        assert romfs.read_file(path) == data


def test_roundtrip_nested_directories() -> None:
    files = {"a/b/c/deep.bin": b"deep content"}
    blob = RomFSBuilder().build(files)
    romfs = RomFS(blob)
    assert romfs.read_file("a/b/c/deep.bin") == b"deep content"


def test_add_file() -> None:
    blob2 = RomFSBuilder().build({"existing.bin": b"original", "new.bin": b"new content"})
    romfs = RomFS(blob2)
    assert romfs.read_file("existing.bin") == b"original"
    assert romfs.read_file("new.bin") == b"new content"


def test_delete_file() -> None:
    blob = RomFSBuilder().build({"keep.bin": b"keep"})
    romfs = RomFS(blob)
    assert romfs.read_file("keep.bin") == b"keep"
    with pytest.raises((FileNotFoundError, ValueError, KeyError)):
        romfs.read_file("gone.bin")


# ── Driver round-trip tests ───────────────────────────────────────────────────


def _make_romfs_buf(path: str, raw_data: bytes) -> "BinaryBuffer":
    """Build a minimal ROMFS BinaryBuffer containing a single compressed file."""
    compressed = compress_lz11(raw_data)
    blob = RomFSBuilder().build({path: compressed})
    buf = BinaryBuffer.__new__(BinaryBuffer)
    buf._path = Path("test.romfs")
    buf._shadow = bytearray(blob)
    return buf


def test_fe13_pack_table_commits() -> None:
    from binforge.drivers.n3ds.fe13 import FE13Driver

    person_raw = bytearray(108 * 85)
    person_raw[0x04] = 42
    buf = _make_romfs_buf("GameData/Person.bin.lz", bytes(person_raw))
    drv = FE13Driver(buf)
    rows = drv.parse_table("characters")
    assert rows[0].hp == 42
    rows[0].hp = 99
    drv.pack_table("characters", rows)
    drv2 = FE13Driver(buf)
    rows2 = drv2.parse_table("characters")
    assert rows2[0].hp == 99


def test_fe14_pack_table_commits() -> None:
    from binforge.drivers.n3ds.fe14 import FE14Driver

    person_raw = bytearray(84 * 130)
    person_raw[0x04] = 77
    buf = _make_romfs_buf("GameData/Person.bin.lz", bytes(person_raw))
    drv = FE14Driver(buf)
    rows = drv.parse_table("characters")
    assert rows[0].hp == 77
    rows[0].hp = 55
    drv.pack_table("characters", rows)
    drv2 = FE14Driver(buf)
    rows2 = drv2.parse_table("characters")
    assert rows2[0].hp == 55


def test_fe15_pack_table_commits() -> None:
    from binforge.drivers.n3ds.fe15 import FE15Driver

    person_raw = bytearray(72 * 50)
    person_raw[0x04] = 33
    buf = _make_romfs_buf("GameData/Person.bin.lz", bytes(person_raw))
    drv = FE15Driver(buf)
    rows = drv.parse_table("characters")
    assert rows[0].hp == 33
    rows[0].hp = 11
    drv.pack_table("characters", rows)
    drv2 = FE15Driver(buf)
    rows2 = drv2.parse_table("characters")
    assert rows2[0].hp == 11
