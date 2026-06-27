"""Run once to generate fe7_chars.bin: uv run python tests/fixtures/gen_fe7_fixture.py"""
import struct
from pathlib import Path

# 3 synthetic character rows, 52 bytes each
# Resembles Lyn/Eliwood/Hector base stats (approximate, not exact)
CHARS = [
    dict(name_ptr=0x0847A820, hp=20, str=4, skl=4, spd=5, lck=5, def_=2, res=0, mov=5, con=5, aid=4, affin=0, class_id=5, level=1, exp=0),
    dict(name_ptr=0x0847A840, hp=16, str=4, skl=5, spd=5, lck=7, def_=5, res=0, mov=5, con=7, aid=6, affin=0, class_id=1, level=1, exp=0),
    dict(name_ptr=0x0847A860, hp=23, str=8, skl=2, spd=4, lck=4, def_=8, res=2, mov=5, con=14, aid=13, affin=0, class_id=3, level=1, exp=0),
]

out = bytearray()
for c in CHARS:
    row = bytearray(52)
    struct.pack_into("<I", row, 0x00, c["name_ptr"])
    row[0x04] = c["hp"]
    row[0x05] = c["str"]
    row[0x06] = c["skl"]
    row[0x07] = c["spd"]
    row[0x08] = c["lck"]
    row[0x09] = c["def_"]
    row[0x0A] = c["res"]
    row[0x0B] = c["mov"]
    row[0x0C] = c["con"]
    row[0x0D] = c["aid"]
    row[0x0E] = c["affin"]
    row[0x0F] = c["class_id"]
    row[0x10] = c["level"]
    row[0x11] = c["exp"]
    out += row

Path(__file__).parent.joinpath("fe7_chars.bin").write_bytes(bytes(out))
print(f"Written {len(out)} bytes")
