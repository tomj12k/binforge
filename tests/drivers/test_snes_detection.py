import tempfile
from pathlib import Path
from binforge.core.engine import BinaryBuffer
from binforge.drivers.snes.fe4 import FE4Driver
from binforge.drivers.snes.fe5 import FE5Driver


def _fake_snes(title: bytes) -> BinaryBuffer:
    data = bytearray(0x8000)
    data[0x7FC0:0x7FC0 + 18] = title
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
    buf = _fake_snes(b"FIREEMBLEM5       ")
    assert FE5Driver(buf).detect(buf)
    assert not FE4Driver(buf).detect(buf)
