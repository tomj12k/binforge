import pytest
from binforge.errors import RomFSBuildError
from binforge.drivers.n3ds.romfs_builder import RomFSBuilder


def test_duplicate_path_raises() -> None:
    builder = RomFSBuilder()
    # build() with duplicate keys isn't possible via dict, but duplicate
    # path normalisation (e.g. leading slash vs no slash) should raise
    with pytest.raises(RomFSBuildError):
        builder.build({"/foo.bin": b"a", "foo.bin": b"b"})
