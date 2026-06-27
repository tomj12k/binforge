import tempfile
from pathlib import Path
from binforge.core.engine import BinaryBuffer
from binforge.drivers.snes.fe4 import FE4Driver
from binforge.drivers.snes.fe5 import FE5Driver


def _fake_snes(title: bytes) -> BinaryBuffer:
    data = bytearray(0x8000)
    data[0x7FC0 : 0x7FC0 + len(title)] = title
    p = Path(tempfile.mktemp(suffix=".sfc"))
    p.write_bytes(bytes(data))
    buf = BinaryBuffer(p)
    p.unlink()
    return buf


def test_fe4_detect():
    buf = _fake_snes(b"FIRE EMBLEM       ")
    assert FE4Driver(buf).detect(buf)
    assert not FE5Driver(buf).detect(buf)


def test_fe5_detect():
    buf = _fake_snes(b"FIRE EMBLEM 776     ")
    assert FE5Driver(buf).detect(buf)
    assert not FE4Driver(buf).detect(buf)


def test_fe5_detect_known_header() -> None:
    """Verify FE5Driver detects the documented Thracia 776 header bytes."""
    import struct
    from pathlib import Path
    from binforge.core.engine import BinaryBuffer
    from binforge.drivers.snes.fe5 import FE5Driver

    rom = bytearray(0x10000)
    title = b"FIRE EMBLEM 776     "  # 20 chars; SNES title = 21 bytes at 0x7FC0
    assert len(title) == 20
    # SNES header title is 21 bytes; pad to 21
    title_padded = title + b" "
    rom[0x7FC0 : 0x7FC0 + 21] = title_padded

    buf = BinaryBuffer.__new__(BinaryBuffer)
    buf._path = Path("fe5_test.sfc")
    buf._shadow = bytearray(rom)
    drv = FE5Driver.__new__(FE5Driver)
    assert drv.detect(buf) is True


def test_fe5_detect_rejects_wrong_header() -> None:
    from pathlib import Path
    from binforge.core.engine import BinaryBuffer
    from binforge.drivers.snes.fe5 import FE5Driver

    rom = bytearray(0x10000)
    rom[0x7FC0 : 0x7FC0 + 21] = b"TOTALLY DIFFERENT    "

    buf = BinaryBuffer.__new__(BinaryBuffer)
    buf._path = Path("fe5_wrong.sfc")
    buf._shadow = bytearray(rom)
    drv = FE5Driver.__new__(FE5Driver)
    assert drv.detect(buf) is False
