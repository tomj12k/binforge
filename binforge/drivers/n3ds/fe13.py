from __future__ import annotations

import struct
from pathlib import Path

from binforge.core.compression import compress_lz11, decompress_lz11
from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, u8, u32
from binforge.drivers.base import FormatDriver
from binforge.drivers.n3ds.romfs import RomFS
from binforge.drivers.n3ds.romfs_builder import RomFSBuilder
from binforge.errors import DecompressionError
from binforge.registry import register

_PERSON_PATH = "GameData/Person.bin.lz"
_3DS_MAGIC = b"IVFC"  # ROMFS magic at byte 0 of the ROMFS blob


@register
class FE13Driver(FormatDriver):
    """Fire Emblem: Awakening (FE13) — 3DS, little-endian.

    Expects the ROMFS blob as input, not the raw CIA.
    Extract with: ctrtool --romfsdir=romfs/ game.cia
    Then pass the ROMFS binary directly to binforge.open().
    """

    MAGIC = _3DS_MAGIC
    ENDIAN = "little"
    POINTER_BASE = 0x000000
    _PERSON_PATH = _PERSON_PATH

    def __init__(self, buf: BinaryBuffer) -> None:
        super().__init__(buf)
        self._romfs: RomFS | None = None
        self._person_data: bytes | None = None

    def detect(self, buf: BinaryBuffer) -> bool:
        """Return True if buf looks like a FE13 ROMFS blob."""
        if buf.read_bytes(0, 4) != _3DS_MAGIC:
            return False
        return self._has_awakening_marker(buf)

    _FE13_PERSON_SIZE = 108 * 85  # 9180 bytes — unique to Awakening

    def _has_awakening_marker(self, buf: BinaryBuffer) -> bool:
        try:
            romfs = RomFS(bytes(buf._shadow))
            compressed = romfs.read_file(_PERSON_PATH)
            decompressed = decompress_lz11(compressed)
            return len(decompressed) == self._FE13_PERSON_SIZE
        except (DecompressionError, ValueError, OSError, struct.error):
            return False

    def _get_person_data(self) -> bytes:
        if self._person_data is None:
            romfs = RomFS(bytes(self._buf._shadow))
            compressed = romfs.read_file(_PERSON_PATH)
            self._person_data = decompress_lz11(compressed)
        return self._person_data

    def tables(self) -> dict[str, TableDef]:
        """Return table definitions for FE13 character data."""
        return {
            "characters": TableDef(
                offset=0x00000000,  # offset within decompressed Person.bin
                row_size=108,
                count=85,
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
                    Field("mov", u8, 0x0C),
                ],
            ),
        }

    def parse_table(self, name: str) -> list:  # type: ignore[override]
        """Parse a table from the decompressed Person.bin staging buffer."""
        person_buf = BinaryBuffer.__new__(BinaryBuffer)
        person_buf._path = Path("Person.bin")
        person_buf._shadow = bytearray(self._get_person_data())
        old_buf = self._buf
        self._buf = person_buf
        try:
            return super().parse_table(name)
        finally:
            self._buf = old_buf

    def pack_table(self, name: str, rows: list) -> None:  # type: ignore[override]
        """Pack edits and rebuild the ROMFS container.

        Serialises *rows* into the decompressed Person.bin staging buffer,
        recompresses it, then rebuilds the full IVFC-wrapped ROMFS blob so
        subsequent :meth:`parse_table` calls see the updated data.

        :param name: Table name (must be ``"characters"``).
        :param rows: Row objects previously returned by :meth:`parse_table`.
        """
        person_data = bytearray(self._get_person_data())
        person_buf = BinaryBuffer.__new__(BinaryBuffer)
        person_buf._path = Path("Person.bin")
        person_buf._shadow = person_data
        old_buf = self._buf
        self._buf = person_buf
        try:
            super().pack_table(name, rows)
        finally:
            self._buf = old_buf
        new_compressed = compress_lz11(bytes(person_data))
        new_romfs = self._rebuild_romfs({self._PERSON_PATH: new_compressed})
        self._buf._shadow = bytearray(new_romfs)
        self._person_data = bytes(person_data)

    def _rebuild_romfs(self, modified: dict[str, bytes | None]) -> bytes:
        """Extract all files from the current ROMFS, merge modifications, rebuild.

        :param modified: Map of virtual path to new content, or ``None`` to delete.
        :returns: New IVFC-wrapped ROMFS blob.
        """
        romfs = RomFS(bytes(self._buf._shadow))
        current: dict[str, bytes | None] = {
            path: romfs.read_file(path) for path in romfs.list_files()
        }
        current.update(modified)
        return RomFSBuilder().build(current)
