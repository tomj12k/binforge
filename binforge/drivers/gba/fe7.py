from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, ptr, u8
from binforge.drivers.base import FormatDriver
from binforge.registry import register


@register
class FE7Driver(FormatDriver):
    """Fire Emblem: Blazing Blade (FE7) — GBA, little-endian."""

    MAGIC = b"FIRE EMBLEM\x00"
    ENDIAN = "little"
    POINTER_BASE = 0x08000000

    def detect(self, buf: BinaryBuffer) -> bool:
        return buf.read_bytes(0xAC, 4) == b"AFEE"

    def tables(self) -> dict[str, TableDef]:
        return {
            "characters": TableDef(
                offset=0x0803D6C0,
                row_size=52,
                count=256,
                fields=[
                    Field("name_ptr", ptr, 0x00),
                    Field("hp",       u8,  0x04),
                    Field("str",      u8,  0x05),
                    Field("skl",      u8,  0x06),
                    Field("spd",      u8,  0x07),
                    Field("lck",      u8,  0x08),
                    Field("def_",     u8,  0x09),
                    Field("res",      u8,  0x0A),
                    Field("mov",      u8,  0x0B),
                    Field("con",      u8,  0x0C),
                    Field("aid",      u8,  0x0D),
                    Field("affin",    u8,  0x0E),
                    Field("class_id", u8,  0x0F),
                    Field("level",    u8,  0x10),
                    Field("exp",      u8,  0x11),
                ],
            ),
            "classes": TableDef(
                offset=0x08047BA0,
                row_size=84,
                count=64,
                fields=[
                    Field("name_ptr", ptr, 0x00),
                    Field("hp",       u8,  0x04),
                    Field("str",      u8,  0x05),
                    Field("skl",      u8,  0x06),
                    Field("spd",      u8,  0x07),
                    Field("def_",     u8,  0x08),
                    Field("res",      u8,  0x09),
                    Field("mov",      u8,  0x0A),
                    Field("con",      u8,  0x0B),
                ],
            ),
            "items": TableDef(
                offset=0x08063E18,
                row_size=36,
                count=256,
                fields=[
                    Field("name_ptr", ptr, 0x00),
                    Field("uses",     u8,  0x04),
                    Field("might",    u8,  0x05),
                    Field("hit",      u8,  0x06),
                    Field("crit",     u8,  0x07),
                    Field("range_lo", u8,  0x08),
                    Field("range_hi", u8,  0x09),
                ],
            ),
            "weapons": TableDef(
                offset=0x0808D3A8,
                row_size=12,
                count=64,
                fields=[
                    Field("rank",     u8,  0x00),
                    Field("exp",      u8,  0x01),
                ],
            ),
        }
