from __future__ import annotations

from binforge.core.compression import decompress_lz11
from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, u8, u32
from binforge.drivers.n3ds.fe13 import FE13Driver
from binforge.drivers.n3ds.romfs import RomFS
from binforge.registry import register

_FATES_PATH = "GameData/Person.bin.lz"


@register
class FE14Driver(FE13Driver):
    """Fire Emblem Fates (FE14) — 3DS, little-endian."""

    _PERSON_PATH = _FATES_PATH

    def detect(self, buf: BinaryBuffer) -> bool:
        if buf.read_bytes(0, 4) != b"IVFC":
            return False
        try:
            romfs = RomFS(bytes(buf._shadow))
            data = decompress_lz11(romfs.read_file(_FATES_PATH))
            return len(data) > 0 and data[0:4] != b"\x00\x00\x00\x00"
        except Exception:
            return False

    def tables(self) -> dict[str, TableDef]:
        return {
            "characters": TableDef(
                offset=0x00000000,
                row_size=84,
                count=130,
                fields=[
                    Field("name_hash", u32, 0x00),
                    Field("hp", u8, 0x04),
                    Field("str", u8, 0x05),
                    Field("mag", u8, 0x06),
                    Field("skl", u8, 0x07),
                    Field("spd", u8, 0x08),
                    Field("lck", u8, 0x09),
                    Field("def_", u8, 0x0A),
                    Field("res", u8, 0x0B),
                ],
            ),
        }
