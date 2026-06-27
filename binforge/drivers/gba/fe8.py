from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, str_ptr, u8

from binforge.drivers.base import FormatDriver
from binforge.drivers.gba.codec_fe8 import FE8_CODEC
from binforge.registry import register


@register
class FE8Driver(FormatDriver):
    """Fire Emblem: The Sacred Stones (FE8) — GBA, little-endian."""

    MAGIC = b"FIRE EMBLEM\x00"
    ENDIAN = "little"
    POINTER_BASE = 0x08000000
    TEXT_CODEC = FE8_CODEC
    _GAME_CODE = b"BE8E"

    def detect(self, buf: BinaryBuffer) -> bool:
        return buf.read_bytes(0xAC, 4) == self._GAME_CODE

    def tables(self) -> dict[str, TableDef]:
        return {
            "characters": TableDef(
                offset=0x08013E8C,
                row_size=52,
                count=256,
                fields=[
                    Field("name_ptr", str_ptr, 0x00),
                    Field("hp", u8, 0x04),
                    Field("str", u8, 0x05),
                    Field("skl", u8, 0x06),
                    Field("spd", u8, 0x07),
                    Field("lck", u8, 0x08),
                    Field("def_", u8, 0x09),
                    Field("res", u8, 0x0A),
                    Field("mov", u8, 0x0B),
                    Field("con", u8, 0x0C),
                    Field("class_id", u8, 0x0F),
                    Field("level", u8, 0x10),
                ],
            ),
            "classes": TableDef(
                offset=0x08030C28,
                row_size=84,
                count=64,
                fields=[
                    Field("name_ptr", str_ptr, 0x00),
                    Field("hp", u8, 0x04),
                    Field("str", u8, 0x05),
                    Field("skl", u8, 0x06),
                    Field("spd", u8, 0x07),
                    Field("def_", u8, 0x08),
                    Field("res", u8, 0x09),
                    Field("mov", u8, 0x0A),
                ],
            ),
            "items": TableDef(
                offset=0x08040304,
                row_size=36,
                count=256,
                fields=[
                    Field("name_ptr", str_ptr, 0x00),
                    Field("uses", u8, 0x04),
                    Field("might", u8, 0x05),
                    Field("hit", u8, 0x06),
                    Field("crit", u8, 0x07),
                ],
            ),
            "skills": TableDef(  # unverified
                offset=0x0804F830,
                row_size=8,
                count=64,
                fields=[
                    Field("id", u8, 0x00),
                    Field("effect", u8, 0x01),
                    Field("type", u8, 0x02),
                ],
            ),
            "chapters": TableDef(  # unverified
                offset=0x08069450,
                row_size=60,
                count=46,
                fields=[
                    Field("id", u8, 0x00),
                    Field("map_id", u8, 0x01),
                    Field("music", u8, 0x02),
                ],
            ),
        }
