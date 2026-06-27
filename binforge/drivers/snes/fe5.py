from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, u8, u16
from binforge.drivers.base import FormatDriver
from binforge.registry import register

_FE5_TITLE = b"FIREEMBLEM5       "  # 18 bytes at 0x7FC0 — verify against your ROM


@register
class FE5Driver(FormatDriver):
    """Fire Emblem: Thracia 776 (FE5) — SNES, big-endian."""

    MAGIC = _FE5_TITLE
    ENDIAN = "big"
    POINTER_BASE = 0x000000

    def detect(self, buf: BinaryBuffer) -> bool:
        return buf.read_bytes(0x7FC0, 18) == _FE5_TITLE

    def tables(self) -> dict[str, TableDef]:
        return {
            "characters": TableDef(
                offset=0x0E5A00,
                row_size=36,
                count=52,
                fields=[
                    Field("char_id", u16, 0x00),
                    Field("hp", u8, 0x02),
                    Field("str", u8, 0x03),
                    Field("mag", u8, 0x04),
                    Field("skl", u8, 0x05),
                    Field("spd", u8, 0x06),
                    Field("lck", u8, 0x07),
                    Field("def_", u8, 0x08),
                    Field("res", u8, 0x09),
                    Field("mov", u8, 0x0A),
                ],
            ),
        }
