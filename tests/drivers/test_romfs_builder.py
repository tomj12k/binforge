import pytest
from binforge.errors import RomFSBuildError
from binforge.drivers.n3ds.romfs_builder import RomFSBuilder


def test_duplicate_path_raises() -> None:
    builder = RomFSBuilder()
    # build() with duplicate keys isn't possible via dict, but duplicate
    # path normalisation (e.g. leading slash vs no slash) should raise
    with pytest.raises(RomFSBuildError):
        builder.build({"/foo.bin": b"a", "foo.bin": b"b"})


def _build(files: dict[str, bytes | None]) -> object:
    """Helper: return root _DirNode without serialising."""
    from binforge.drivers.n3ds.romfs_builder import RomFSBuilder, _DirNode
    builder = RomFSBuilder()
    norm = builder._normalise(files)
    return builder._build_tree(norm)


def test_tree_single_file() -> None:
    from binforge.drivers.n3ds.romfs_builder import _DirNode, _FileNode
    root = _build({"foo.bin": b"\x01\x02"})
    assert isinstance(root, _DirNode)
    assert root.name == ""
    assert len(root.files) == 1
    assert root.files[0].name == "foo.bin"
    assert root.files[0].data == b"\x01\x02"


def test_tree_nested_dir() -> None:
    from binforge.drivers.n3ds.romfs_builder import _DirNode
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
