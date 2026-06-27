from __future__ import annotations

import struct as _struct
from abc import ABC, abstractmethod
from typing import Any

from binforge.core.engine import BinaryBuffer
from binforge.core.pointer import PointerTable
from binforge.core.struct_types import FieldType, Struct, TableDef
from binforge.errors import TableNotFoundError


class FormatDriver(ABC):
    MAGIC: bytes = b""
    ENDIAN: str = "little"
    POINTER_BASE: int = 0x00000000

    def __init__(self, buf: BinaryBuffer) -> None:
        self._buf = buf
        self._ptr = PointerTable(self.POINTER_BASE, self.ENDIAN)

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
            kwargs: dict[str, Any] = {}
            for f in tdef.fields:
                kwargs[f.name] = self._read_field(row_start + f.offset, f.ftype)
            rows.append(Struct(list(kwargs.keys()), **kwargs))
        return rows

    def pack_table(self, name: str, rows: list[Struct]) -> None:
        tdef = self.tables().get(name)
        if tdef is None:
            raise TableNotFoundError(name)
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

    def _read_field(self, offset: int, ft: FieldType) -> Any:
        big = self.ENDIAN == "big"
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
        if ft.is_str:
            encoded = value.encode("ascii")[: ft.size].ljust(ft.size, b"\x00")
            self._buf.patch(offset, encoded)
        else:
            self._buf.patch(offset, _struct.pack(f"{ec}{ft.fmt}", value))
