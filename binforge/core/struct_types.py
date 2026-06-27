from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldType:
    fmt: str
    size: int
    is_ptr: bool = False
    is_str: bool = False


u8  = FieldType("B", 1)
u16 = FieldType("H", 2)
u32 = FieldType("I", 4)
i8  = FieldType("b", 1)
i16 = FieldType("h", 2)
i32 = FieldType("i", 4)
ptr = FieldType("I", 4, is_ptr=True)


def fixed_str(n: int) -> FieldType:
    return FieldType(f"{n}s", n, is_str=True)


@dataclass
class Field:
    name: str
    ftype: FieldType
    offset: int


@dataclass
class TableDef:
    offset: int
    row_size: int
    count: int
    fields: list[Field]


class Struct:
    def __init__(self, field_names: list[str], **kwargs: Any) -> None:
        self._fields = field_names
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        parts: list[str] = []
        for k in self._fields:
            v = getattr(self, k)
            if isinstance(v, int) and k.endswith("_ptr"):
                parts.append(f"{k}=0x{v:08X}")
            else:
                parts.append(f"{k}={v!r}")
        return f"Struct({', '.join(parts)})"
