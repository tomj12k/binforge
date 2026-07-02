from __future__ import annotations

import struct as _struct
from abc import ABC, abstractmethod
from typing import Any

from binforge.core.engine import BinaryBuffer
from binforge.core.pointer import PointerTable
from binforge.core.struct_types import FieldType, Struct, TableDef
from binforge.core.text import TextCodec
from binforge.errors import PatchSizeError, PointerRangeError, TableNotFoundError


class FormatDriver(ABC):
    MAGIC: bytes = b""
    ENDIAN: str = "little"
    POINTER_BASE: int = 0x00000000
    TEXT_CODEC: TextCodec | None = None

    def __init__(self, buf: BinaryBuffer) -> None:
        self._buf = buf
        self._ptr = PointerTable(self.POINTER_BASE, self.ENDIAN)
        self._pending_raw: dict[str, int] = {}

    @abstractmethod
    def tables(self) -> dict[str, TableDef]: ...

    @abstractmethod
    def detect(self, buf: BinaryBuffer) -> bool: ...

    def table_names(self) -> list[str]:
        return list(self.tables().keys())

    def parse_table(self, name: str) -> list[Struct]:
        tdef = self.tables().get(name)
        if tdef is None:
            raise TableNotFoundError(name)
        file_offset = self._ptr.resolve(tdef.offset)
        rows: list[Struct] = []
        for i in range(tdef.count):
            row_start = file_offset + i * tdef.row_size
            self._pending_raw = {}
            kwargs: dict[str, Any] = {}
            for f in tdef.fields:
                kwargs[f.name] = self._read_field(row_start + f.offset, f.ftype, f.name)
            row = Struct(list(kwargs.keys()), **kwargs)
            row._raw = dict(self._pending_raw)
            rows.append(row)
        return rows

    def pack_table(self, name: str, rows: list[Struct]) -> None:
        tdef = self.tables().get(name)
        if tdef is None:
            raise TableNotFoundError(name)
        if len(rows) > tdef.count:
            raise PatchSizeError(
                tdef.offset + tdef.count * tdef.row_size,
                len(rows) * tdef.row_size,
                len(self._buf._shadow),
            )
        file_offset = self._ptr.resolve(tdef.offset)
        ec = ">" if self.ENDIAN == "big" else "<"
        for i, row in enumerate(rows):
            row_start = file_offset + i * tdef.row_size
            for f in tdef.fields:
                value = getattr(row, f.name)
                self._write_field(row_start + f.offset, f.ftype, value, ec)

    def commit(self, path: str | None = None, in_place: bool = False) -> None:
        self._buf.commit(path, in_place=in_place)

    # ── private helpers ──────────────────────────────────────────────────────

    def _read_field(self, offset: int, ft: FieldType, field_name: str = "") -> Any:
        big = self.ENDIAN == "big"
        if ft.is_str_ptr:
            raw_ptr = self._buf.read_u32(offset, big=big)
            self._pending_raw[field_name] = raw_ptr
            if self.TEXT_CODEC is not None:
                file_off = self._ptr.resolve(raw_ptr)
                raw_bytes = bytearray()
                pos = file_off
                while 0 <= pos < len(self._buf._shadow):
                    b = self._buf.read_u8(pos)
                    if b == 0x00:
                        break
                    raw_bytes.append(b)
                    pos += 1
                return self.TEXT_CODEC.decode_bytes(bytes(raw_bytes))
            return raw_ptr
        if ft.is_str:
            return (
                self._buf.read_bytes(offset, ft.size)
                .rstrip(b"\x00")
                .decode("ascii", errors="replace")
            )
        if ft.size == 1:
            return self._buf.read_i8(offset) if ft.fmt == "b" else self._buf.read_u8(offset)
        if ft.size == 2:
            return (
                self._buf.read_i16(offset, big=big)
                if ft.fmt == "h"
                else self._buf.read_u16(offset, big=big)
            )
        return (
            self._buf.read_i32(offset, big=big)
            if ft.fmt == "i"
            else self._buf.read_u32(offset, big=big)
        )

    def _write_field(self, offset: int, ft: FieldType, value: Any, ec: str) -> None:
        if ft.is_str_ptr:
            if isinstance(value, str) and self.TEXT_CODEC is not None:
                encoded = self.TEXT_CODEC.encode(value)
                big = self.ENDIAN == "big"
                raw_ptr = self._buf.read_u32(offset, big=big)
                file_off = self._ptr.resolve(raw_ptr)
                if not (0 <= file_off < len(self._buf._shadow)):
                    if value == "":
                        # Round-trip of a null/out-of-range pointer: parse
                        # decoded it to "" and nothing was edited — no-op.
                        return
                    raise PointerRangeError(raw_ptr, len(self._buf._shadow))
                existing_len = 0
                while 0 <= file_off + existing_len < len(self._buf._shadow):
                    if self._buf.read_u8(file_off + existing_len) == 0x00:
                        existing_len += 1
                        break
                    existing_len += 1
                if len(encoded) > existing_len:
                    raise PatchSizeError(
                        file_off,
                        len(encoded),
                        existing_len,
                        message=(
                            f"encoded string ({len(encoded)} bytes) longer than "
                            f"existing string span ({existing_len} bytes) "
                            f"at 0x{file_off:08X}"
                        ),
                    )
                # Shorter/equal replacement: encoded already ends with the
                # null terminator; zero-pad the rest of the old span.
                self._buf.patch(
                    file_off, encoded + b"\x00" * (existing_len - len(encoded))
                )
            elif isinstance(value, int):
                big = self.ENDIAN == "big"
                packed = _struct.pack(f"{'>' if big else '<'}I", value)
                self._buf.patch(offset, packed)
            return
        if ft.is_str:
            encoded = value.encode("ascii")[: ft.size].ljust(ft.size, b"\x00")
            self._buf.patch(offset, encoded)
        else:
            self._buf.patch(offset, _struct.pack(f"{ec}{ft.fmt}", value))
