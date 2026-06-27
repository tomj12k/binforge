"""Minimal Nintendo ROMFS (Level 3) extractor."""

import struct
from binforge.errors import DecompressionError

_ROMFS_MAGIC = 0x43465649  # b"IVFC" read as little-endian u32


class RomFS:
    """Read files from a ROMFS blob by virtual path."""

    def __init__(self, data: bytes) -> None:
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != _ROMFS_MAGIC:
            raise DecompressionError(f"ROMFS magic mismatch: 0x{magic:08X}")
        self._data = data
        # Level 3 starts after IVFC header (0x60 bytes) + master hash table
        master_hash_size = struct.unpack_from("<I", data, 0x08)[0]
        self._l3_offset = 0x60 + master_hash_size
        self._l3 = data[self._l3_offset :]
        # Level 3 header
        self._dir_hash_off = struct.unpack_from("<I", self._l3, 0x04)[0]
        self._dir_meta_off = struct.unpack_from("<I", self._l3, 0x0C)[0]
        self._file_hash_off = struct.unpack_from("<I", self._l3, 0x14)[0]
        self._file_meta_off = struct.unpack_from("<I", self._l3, 0x1C)[0]
        self._data_off = struct.unpack_from("<I", self._l3, 0x24)[0]

    def read_file(self, virtual_path: str) -> bytes:
        """Return the raw bytes of a file inside the ROMFS by its virtual path."""
        parts = [p for p in virtual_path.strip("/").split("/") if p]
        dir_entry_off = 0x18  # root directory always at offset 0x18 in dir_meta
        for part in parts[:-1]:
            dir_entry_off = self._find_child_dir(dir_entry_off, part)
        file_entry_off = self._find_file_in_dir(dir_entry_off, parts[-1])
        return self._read_file_entry(file_entry_off)

    def _read_str(self, meta_section: bytes, off: int, length: int) -> str:
        raw = meta_section[off : off + length]
        return raw.decode("utf-16-le", errors="replace")

    def _find_child_dir(self, parent_off: int, name: str) -> int:
        child_off = struct.unpack_from("<I", self._l3, self._dir_meta_off + parent_off + 0x08)[0]
        while child_off != 0xFFFFFFFF:
            name_len = struct.unpack_from("<I", self._l3, self._dir_meta_off + child_off + 0x14)[0]
            entry_name = self._read_str(self._l3, self._dir_meta_off + child_off + 0x18, name_len)
            if entry_name == name:
                return child_off
            child_off = struct.unpack_from("<I", self._l3, self._dir_meta_off + child_off + 0x10)[0]
        raise FileNotFoundError(f"Directory '{name}' not found in ROMFS")

    def _find_file_in_dir(self, dir_off: int, name: str) -> int:
        file_off = struct.unpack_from("<I", self._l3, self._dir_meta_off + dir_off + 0x0C)[0]
        while file_off != 0xFFFFFFFF:
            name_len = struct.unpack_from("<I", self._l3, self._file_meta_off + file_off + 0x1C)[0]
            entry_name = self._read_str(self._l3, self._file_meta_off + file_off + 0x20, name_len)
            if entry_name == name:
                return file_off
            file_off = struct.unpack_from("<I", self._l3, self._file_meta_off + file_off + 0x18)[0]
        raise FileNotFoundError(f"File '{name}' not found in ROMFS")

    def _read_file_entry(self, file_off: int) -> bytes:
        data_off = struct.unpack_from("<Q", self._l3, self._file_meta_off + file_off + 0x08)[0]
        data_size = struct.unpack_from("<Q", self._l3, self._file_meta_off + file_off + 0x10)[0]
        start = self._data_off + data_off
        return bytes(self._l3[start : start + int(data_size)])
