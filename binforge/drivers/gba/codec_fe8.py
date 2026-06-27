"""FE8 (Fire Emblem: Sacred Stones) GBA text encoding table.

FE8 uses the same Western encoding as FE7.
"""
from binforge.core.text import TextCodec
from binforge.drivers.gba.codec_fe7 import _TABLE

FE8_CODEC = TextCodec(_TABLE)
