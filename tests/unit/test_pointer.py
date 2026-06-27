import pytest
from binforge.core.pointer import PointerTable
from binforge.errors import PointerRangeError


def test_gba_resolve():
    pt = PointerTable(base=0x08000000, endian="little")
    assert pt.resolve(0x0803A820) == 0x0003A820


def test_gba_rebase():
    pt = PointerTable(base=0x08000000, endian="little")
    assert pt.rebase(0x0003A820) == 0x0803A820


def test_snes_resolve_zero_base():
    pt = PointerTable(base=0x000000, endian="big")
    assert pt.resolve(0x012345) == 0x012345


def test_3ds_resolve_zero_base():
    pt = PointerTable(base=0x000000, endian="little")
    assert pt.resolve(0xABCD) == 0xABCD


def test_check_bounds_valid():
    pt = PointerTable(base=0x08000000, endian="little")
    pt.check_bounds(0x08000000, file_size=1024)  # resolves to 0, within 1024


def test_check_bounds_too_high():
    pt = PointerTable(base=0x08000000, endian="little")
    with pytest.raises(PointerRangeError):
        pt.check_bounds(0x08000000 + 1024, file_size=1024)  # resolves to 1024 == size


def test_check_bounds_below_base():
    pt = PointerTable(base=0x08000000, endian="little")
    with pytest.raises(PointerRangeError):
        pt.check_bounds(0x07FFFFFF, file_size=1024)  # resolves to -1
