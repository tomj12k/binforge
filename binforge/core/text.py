"""GBA Fire Emblem text codec — per-game byte ↔ Unicode character mapping."""

from __future__ import annotations

from binforge.errors import EncodingError


class TextCodec:
    """Encode and decode GBA FE game text using a game-specific byte table.

    :param table: Mapping of byte value (0x01–0xFF) → Unicode character.
                  0x00 is always the null terminator and must not appear in the table.
    """

    def __init__(self, table: dict[int, str]) -> None:
        self._decode_table = table
        self._encode_table: dict[str, int] = {v: k for k, v in table.items()}

    def decode_bytes(self, data: bytes) -> str:
        """Decode raw bytes to a Python string, stopping at the first 0x00 byte.

        Unknown byte values are replaced with U+FFFD (replacement character).

        :param data: Raw bytes starting at the string's first character.
        :returns: Decoded string (without null terminator).
        """
        result: list[str] = []
        for b in data:
            if b == 0x00:
                break
            result.append(self._decode_table.get(b, ""))
        return "".join(result)

    def encode(self, text: str) -> bytes:
        """Encode a Python string to game bytes, appending a null terminator.

        :param text: String to encode.
        :returns: Encoded bytes ending with 0x00.
        :raises EncodingError: If any character has no mapping in the table.
        """
        out = bytearray()
        for ch in text:
            if ch not in self._encode_table:
                raise EncodingError(ch)
            out.append(self._encode_table[ch])
        out.append(0x00)
        return bytes(out)
