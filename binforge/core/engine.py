"""Binary file reading and patching engine."""

import struct
from pathlib import Path

from binforge.errors import CommitError, PatchSizeError


class BinaryBuffer:
    """Read and patch binary files with lazy in-memory shadow buffer.

    Loads a file into memory on construction, allowing reads and patches
    without touching disk until explicit commit.
    """

    def __init__(self, path: str | Path) -> None:
        """Initialize BinaryBuffer from a file path.

        :param path: Path to binary file to load
        :type path: str | Path
        """
        self._path = Path(path)
        self._shadow = bytearray(self._path.read_bytes())

    def __len__(self) -> int:
        """Return the size of the buffer in bytes.

        :rtype: int
        """
        return len(self._shadow)

    def read_u8(self, offset: int) -> int:
        """Read unsigned 8-bit integer at offset.

        :param offset: Byte offset in buffer
        :type offset: int
        :returns: Unsigned 8-bit value
        :rtype: int
        """
        return self._shadow[offset]

    def read_u16(self, offset: int, big: bool = False) -> int:
        """Read unsigned 16-bit integer at offset.

        :param offset: Byte offset in buffer
        :type offset: int
        :param big: If True, use big-endian; else little-endian
        :type big: bool
        :returns: Unsigned 16-bit value
        :rtype: int
        """
        fmt = ">H" if big else "<H"
        return struct.unpack_from(fmt, self._shadow, offset)[0]

    def read_u32(self, offset: int, big: bool = False) -> int:
        """Read unsigned 32-bit integer at offset.

        :param offset: Byte offset in buffer
        :type offset: int
        :param big: If True, use big-endian; else little-endian
        :type big: bool
        :returns: Unsigned 32-bit value
        :rtype: int
        """
        fmt = ">I" if big else "<I"
        return struct.unpack_from(fmt, self._shadow, offset)[0]

    def read_i8(self, offset: int) -> int:
        """Read signed 8-bit integer at offset.

        :param offset: Byte offset in buffer
        :type offset: int
        :returns: Signed 8-bit value
        :rtype: int
        """
        return struct.unpack_from("b", self._shadow, offset)[0]

    def read_i16(self, offset: int, big: bool = False) -> int:
        """Read signed 16-bit integer at offset.

        :param offset: Byte offset in buffer
        :type offset: int
        :param big: If True, use big-endian; else little-endian
        :type big: bool
        :returns: Signed 16-bit value
        :rtype: int
        """
        fmt = ">h" if big else "<h"
        return struct.unpack_from(fmt, self._shadow, offset)[0]

    def read_i32(self, offset: int, big: bool = False) -> int:
        """Read signed 32-bit integer at offset.

        :param offset: Byte offset in buffer
        :type offset: int
        :param big: If True, use big-endian; else little-endian
        :type big: bool
        :returns: Signed 32-bit value
        :rtype: int
        """
        fmt = ">i" if big else "<i"
        return struct.unpack_from(fmt, self._shadow, offset)[0]

    def read_bytes(self, offset: int, size: int) -> bytes:
        """Read raw bytes from buffer.

        :param offset: Byte offset in buffer
        :type offset: int
        :param size: Number of bytes to read
        :type size: int
        :returns: Bytes read from buffer
        :rtype: bytes
        """
        return bytes(self._shadow[offset : offset + size])

    def patch(self, offset: int, data: bytes) -> None:
        """Apply a byte patch to the shadow buffer.

        Does not touch disk. Raises PatchSizeError if patch exceeds bounds.

        :param offset: Byte offset to start patch
        :type offset: int
        :param data: Bytes to write
        :type data: bytes
        :raises PatchSizeError: If patch extends beyond file size
        """
        end = offset + len(data)
        if end > len(self._shadow):
            raise PatchSizeError(offset, len(data), len(self._shadow))
        self._shadow[offset:end] = data

    def commit(self, path: str | Path | None = None, in_place: bool = False) -> None:
        """Write shadow buffer to disk.

        Either path or in_place must be specified. If path is given, writes to
        that location (original file untouched). If in_place=True, overwrites
        the original file.

        :param path: Destination path (if None, uses original path with in_place=True)
        :type path: str | Path | None
        :param in_place: If True and path is None, overwrite original file
        :type in_place: bool
        :raises CommitError: If neither path nor in_place is specified, or on write error
        """
        if path is None and not in_place:
            raise CommitError(str(self._path), "must specify path or pass in_place=True")
        dest = Path(path) if path is not None else self._path
        try:
            dest.write_bytes(bytes(self._shadow))
        except OSError as e:
            raise CommitError(str(dest), str(e)) from e
