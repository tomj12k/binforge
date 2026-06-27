import struct
import tempfile
from pathlib import Path

from binforge.core.engine import BinaryBuffer
from binforge.drivers.gba.fe6 import FE6Driver
from binforge.drivers.gba.fe7 import FE7Driver
from binforge.drivers.gba.fe8 import FE8Driver


def _fake_rom(game_code: bytes) -> BinaryBuffer:
    data = bytearray(0x200)
    data[0xAC:0xAC + 4] = game_code
    p = Path(tempfile.mktemp(suffix=".gba"))
    p.write_bytes(bytes(data))
    buf = BinaryBuffer(p)
    p.unlink()
    return buf


def test_fe6_detect():
    buf = _fake_rom(b"AFEJ")
    assert FE6Driver(buf).detect(buf)
    assert not FE7Driver(buf).detect(buf)
    assert not FE8Driver(buf).detect(buf)


def test_fe7_detect():
    buf = _fake_rom(b"AFEE")
    assert FE7Driver(buf).detect(buf)
    assert not FE6Driver(buf).detect(buf)
    assert not FE8Driver(buf).detect(buf)


def test_fe8_detect():
    buf = _fake_rom(b"BE8E")
    assert FE8Driver(buf).detect(buf)
    assert not FE6Driver(buf).detect(buf)
    assert not FE7Driver(buf).detect(buf)
