import pytest
from binforge.core.compression import (
    compress_lz10,
    compress_lz11,
    compress_rle,
    decompress_lz10,
    decompress_lz11,
    decompress_rle,
)
from binforge.errors import DecompressionError


def test_lz10_round_trip():
    original = b"FIRE EMBLEM" * 10
    compressed = compress_lz10(original)
    assert compressed[0] == 0x10  # magic byte
    assert decompress_lz10(compressed) == original


def test_lz10_bad_magic():
    with pytest.raises(DecompressionError):
        decompress_lz10(b"\x11\x00\x00\x00")  # LZ11 magic, not LZ10


def test_lz11_round_trip():
    original = b"AWAKENING" * 15
    compressed = compress_lz11(original)
    assert compressed[0] == 0x11  # magic byte
    assert decompress_lz11(compressed) == original


def test_lz11_bad_magic():
    with pytest.raises(DecompressionError):
        decompress_lz11(b"\x10\x00\x00\x00")


def test_rle_round_trip():
    original = b"\xaa\xaa\xaa\xbb\xcc"
    compressed = compress_rle(original)
    assert decompress_rle(compressed) == original


def test_lz10_preserves_size():
    original = bytes(range(256))
    assert decompress_lz10(compress_lz10(original)) == original


def test_lz11_preserves_size():
    original = bytes(range(256))
    assert decompress_lz11(compress_lz11(original)) == original


def test_lz10_truncated_raises_decompression_error():
    """Truncated LZ10 stream (valid header, empty body) must raise DecompressionError."""
    # Header declares 10 bytes of output but provides no compressed body
    header = bytes([0x10, 0x0A, 0x00, 0x00])
    with pytest.raises(DecompressionError):
        decompress_lz10(header)


def test_lz11_truncated_raises_decompression_error():
    """Truncated LZ11 stream (valid header, empty body) must raise DecompressionError."""
    # Header declares 10 bytes of output but provides no compressed body
    header = bytes([0x11, 0x0A, 0x00, 0x00])
    with pytest.raises(DecompressionError):
        decompress_lz11(header)
