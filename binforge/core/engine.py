"""Binary file reading and patching engine."""

import struct
from pathlib import Path

from binforge.errors import CommitError, PatchSizeError


def diff_spans(a: bytes, b: bytes, gap: int = 4) -> list[tuple[int, int]]:
    """Return (offset, length) spans where two byte strings differ.

    Adjacent/nearby differing spans separated by ``gap`` or fewer equal
    bytes are merged into one span. Only the common prefix length
    ``min(len(a), len(b))`` is scanned; callers must handle length
    mismatches themselves.

    :param a: First byte string
    :type a: bytes
    :param b: Second byte string
    :type b: bytes
    :param gap: Maximum run of equal bytes to absorb when merging spans
    :type gap: int
    :returns: Merged differing spans, empty if identical
    :rtype: list[tuple[int, int]]
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            start = i
            while i < n and a[i] != b[i]:
                i += 1
            if spans and start - (spans[-1][0] + spans[-1][1]) <= gap:
                prev_start, _ = spans[-1]
                spans[-1] = (prev_start, i - prev_start)
            else:
                spans.append((start, i - start))
        else:
            i += 1
    return spans


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
        self._path: Path | None = Path(path)
        self._shadow = bytearray(self._path.read_bytes())
        # Immutable snapshot of the file as loaded, kept so dirty_ranges()
        # can diff against the pristine contents. This doubles resident
        # memory (e.g. ~2 GB for a 1 GB CIA) — acceptable for now.
        self._original: bytes = bytes(self._shadow)

    @classmethod
    def from_bytes(cls, data: bytes, name: str = "<memory>") -> "BinaryBuffer":
        """Construct an in-memory buffer not backed by a file.

        ``commit()`` on such a buffer raises :class:`CommitError` unless an
        explicit destination path is given.

        :param data: Initial buffer contents
        :type data: bytes
        :param name: Display name used in error messages
        :type name: str
        :returns: New in-memory buffer
        :rtype: BinaryBuffer
        """
        buf = cls.__new__(cls)
        buf._path = None
        buf._name = name
        buf._shadow = bytearray(data)
        buf._original = bytes(data)
        return buf

    def __len__(self) -> int:
        """Return the size of the buffer in bytes.

        :rtype: int
        """
        return len(self._shadow)

    def __bytes__(self) -> bytes:
        """Return the current shadow buffer contents as bytes.

        :rtype: bytes
        """
        return bytes(self._shadow)

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

    def read_cstring(self, offset: int, max_len: int = 4096) -> bytes:
        """Read a NUL-terminated string starting at offset.

        Returns bytes up to (not including) the first 0x00. Stops silently at
        ``max_len`` bytes or the end of the buffer if no terminator is found.

        :param offset: Byte offset to start reading
        :type offset: int
        :param max_len: Maximum number of bytes to scan
        :type max_len: int
        :returns: String bytes without the terminator
        :rtype: bytes
        """
        chunk = self._shadow[offset : offset + max_len]
        nul = chunk.find(0)
        return bytes(chunk if nul < 0 else chunk[:nul])

    def hexdump(self, offset: int = 0, length: int = 256, width: int = 16) -> str:
        """Render a classic hexdump of a region of the buffer.

        Each line: 8-hex-digit offset, hex bytes with a double space at the
        half-way point, and an ASCII gutter (printable 0x20-0x7E, else '.').
        The region is clamped to the end of the buffer.

        :param offset: Starting byte offset
        :type offset: int
        :param length: Number of bytes to dump
        :type length: int
        :param width: Bytes per line
        :type width: int
        :returns: Formatted hexdump (no trailing newline)
        :rtype: str
        :raises ValueError: If ``width`` is less than 1
        """
        if width < 1:
            raise ValueError("width must be >= 1")
        end = min(offset + length, len(self._shadow))
        lines: list[str] = []
        half = width // 2
        for line_off in range(offset, end, width):
            row = self._shadow[line_off : min(line_off + width, end)]
            hex_cells = [f"{b:02x}" for b in row]
            hex_cells += ["  "] * (width - len(row))
            hex_part = " ".join(hex_cells[:half]) + "  " + " ".join(hex_cells[half:])
            ascii_part = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in row)
            lines.append(f"{line_off:08x}  {hex_part}  |{ascii_part}|")
        return "\n".join(lines)

    def find(self, needle: bytes | str, start: int = 0, limit: int = 100) -> list[int]:
        """Find all occurrences of a byte pattern in the buffer.

        :param needle: Pattern to search for. A str is parsed as hex, e.g.
            ``"AF EE 00"`` or ``"afee00"`` (spaces stripped).
        :type needle: bytes | str
        :param start: Offset to start searching from
        :type start: int
        :param limit: Maximum number of match offsets to return
        :type limit: int
        :returns: Offsets of matches, capped at ``limit``
        :rtype: list[int]
        :raises ValueError: If a str needle is not valid hex
        """
        if isinstance(needle, str):
            needle = bytes.fromhex(needle.replace(" ", ""))
        if not needle:
            return []
        offsets: list[int] = []
        pos = start
        while len(offsets) < limit:
            pos = self._shadow.find(needle, pos)
            if pos < 0:
                break
            offsets.append(pos)
            pos += 1
        return offsets

    def dirty_ranges(self) -> list[tuple[int, int]]:
        """Return (offset, length) spans where the shadow differs from the original load-time contents.

        Diffs the shadow against the ORIGINAL contents captured at load time,
        merging adjacent/nearby spans (gap <= 4 bytes). If the shadow length
        has changed (e.g. a 3DS ROMFS rebuild replaces the whole shadow),
        a byte-wise diff is meaningless, so the entire buffer is reported
        dirty as ``[(0, len(shadow))]``. Note that :meth:`commit` does NOT
        reset the baseline: spans remain dirty after a commit.

        :returns: Merged dirty spans, empty if nothing changed
        :rtype: list[tuple[int, int]]
        """
        if len(self._shadow) != len(self._original):
            return [(0, len(self._shadow))]
        return diff_spans(bytes(self._shadow), self._original)

    def replace_contents(self, data: bytes) -> None:
        """Replace the entire shadow buffer (e.g. after a ROMFS rebuild).

        The original snapshot used by :meth:`dirty_ranges` is deliberately
        left untouched: a rebuilt container is legitimately all-dirty
        relative to the file on disk.

        :param data: New complete buffer contents
        :type data: bytes
        """
        self._shadow = bytearray(data)

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
        :raises CommitError: If neither path nor in_place is specified, if the
            buffer is in-memory (no backing file) and no path is given, or on
            write error
        """
        display = str(self._path) if self._path is not None else getattr(self, "_name", "<memory>")
        if path is None and not in_place:
            raise CommitError(display, "must specify path or pass in_place=True")
        if path is None and self._path is None:
            raise CommitError(display, "in-memory buffer has no backing file; specify a path")
        dest = Path(path) if path is not None else self._path
        if dest is None:  # unreachable; narrows type for the write below
            raise CommitError(display, "no destination path")
        try:
            dest.write_bytes(bytes(self._shadow))
        except OSError as e:
            raise CommitError(str(dest), str(e)) from e
