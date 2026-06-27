from __future__ import annotations

import struct

from binforge.core.compression import decompress_lz11
from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, u8, u32
from binforge.drivers.n3ds.fe13 import FE13Driver
from binforge.drivers.n3ds.romfs import RomFS
from binforge.errors import DecompressionError
from binforge.registry import register

_ECHOES_PATH = "GameData/Person.bin.lz"


@register
class FE15Driver(FE13Driver):
    """Fire Emblem Echoes: Shadows of Valentia (FE15) — 3DS, little-endian."""

    _PERSON_PATH = _ECHOES_PATH

    _TABLE_PATHS: dict[str, str] = {
        "characters": _ECHOES_PATH,
        "classes": "GameData/JobData.bin.lz",
    }

    _FE15_PERSON_SIZE = 72 * 50  # 3600 bytes — unique to Echoes

    def detect(self, buf: BinaryBuffer) -> bool:
        # FE15 detection: ROMFS present + Person.bin.lz decompresses to exact FE15 size
        if buf.read_bytes(0, 4) != b"IVFC":
            return False
        try:
            romfs = RomFS(bytes(buf._shadow))
            data = decompress_lz11(romfs.read_file(_ECHOES_PATH))
            return len(data) == self._FE15_PERSON_SIZE
        except (DecompressionError, ValueError, OSError, struct.error):
            return False

    def tables(self) -> dict[str, TableDef]:
        return {
            "characters": TableDef(
                offset=0x00000000,
                row_size=72,
                count=50,
                fields=[
                    Field("name_hash", u32, 0x00),
                    Field("hp", u8, 0x04),
                    Field("atk", u8, 0x05),
                    Field("skl", u8, 0x06),
                    Field("spd", u8, 0x07),
                    Field("lck", u8, 0x08),
                    Field("def_", u8, 0x09),
                    Field("res", u8, 0x0A),
                ],
            ),
            "classes": TableDef(
                offset=0x00000000,
                row_size=80,
                count=36,
                fields=[
                    Field("id", u8, 0x00),
                    Field("move", u8, 0x08),
                ],
            ),
        }
