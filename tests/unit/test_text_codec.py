"""Tests for TextCodec — GBA text encoding/decoding."""
import pytest

from binforge.core.text import TextCodec
from binforge.errors import EncodingError

# Minimal table for testing
_TABLE: dict[int, str] = {
    0x01: "A",
    0x02: "B",
    0x03: "C",
    0x04: "",  # private-use newline control code → PUA U+E001
}

_CODEC = TextCodec(_TABLE)


def test_decode_bytes_simple() -> None:
    assert _CODEC.decode_bytes(b"\x01\x02\x03\x00") == "ABC"


def test_decode_bytes_stops_at_null() -> None:
    assert _CODEC.decode_bytes(b"\x01\x00\x02\x03") == "A"


def test_decode_bytes_empty() -> None:
    assert _CODEC.decode_bytes(b"\x00") == ""


def test_encode_simple() -> None:
    assert _CODEC.encode("ABC") == b"\x01\x02\x03\x00"


def test_encode_unknown_glyph() -> None:
    with pytest.raises(EncodingError) as exc_info:
        _CODEC.encode("Z")
    assert "Z" in str(exc_info.value)


def test_roundtrip_all_glyphs() -> None:
    all_chars = "".join(_TABLE.values())
    encoded = _CODEC.encode(all_chars)
    decoded = _CODEC.decode_bytes(encoded)
    assert decoded == all_chars


def test_control_code_roundtrip() -> None:
    text = "AB"  # newline between A and B
    assert _CODEC.decode_bytes(_CODEC.encode(text)) == text
