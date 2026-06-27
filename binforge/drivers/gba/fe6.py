from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, str_ptr, u8
from binforge.drivers.base import FormatDriver
from binforge.drivers.gba.codec_fe6 import FE6_CODEC
from binforge.registry import register


@register
class FE6Driver(FormatDriver):
    """Fire Emblem: Binding Blade (FE6) — GBA, little-endian."""

    MAGIC = b"FIRE EMBLEM\x00"
    ENDIAN = "little"
    POINTER_BASE = 0x08000000
    TEXT_CODEC = FE6_CODEC
    _GAME_CODE = b"AFEJ"

    def detect(self, buf: BinaryBuffer) -> bool:
        return buf.read_bytes(0xAC, 4) == self._GAME_CODE

    def tables(self) -> dict[str, TableDef]:
        return {
            "characters": TableDef(
                offset=0x08035420,
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
                offset=0x08039D04,
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
        }
