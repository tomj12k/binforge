import difflib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldType:
    fmt: str
    size: int
    is_ptr: bool = False
    is_str: bool = False
    is_str_ptr: bool = False


u8 = FieldType("B", 1)
u16 = FieldType("H", 2)
u32 = FieldType("I", 4)
i8 = FieldType("b", 1)
i16 = FieldType("h", 2)
i32 = FieldType("i", 4)
ptr = FieldType("I", 4, is_ptr=True)
str_ptr = FieldType("I", 4, is_ptr=True, is_str_ptr=True)


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
        self._raw: dict[str, int] = {}
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __setattr__(self, name: str, value: Any) -> None:
        """Set a field value, rejecting names that are not known fields.

        Internal (underscore-prefixed) names are always allowed so that
        ``_fields``/``_raw`` can be set during ``__init__``.

        :param name: Attribute name to set.
        :param value: Value to assign.
        :raises AttributeError: If ``name`` is not a known field, with the
            closest matching field name suggested when one exists.
        """
        if name.startswith("_") or name in self.__dict__.get("_fields", ()):
            object.__setattr__(self, name, value)
            return
        fields = self.__dict__.get("_fields", [])
        matches = difflib.get_close_matches(name, fields, n=1)
        hint = f" Did you mean '{matches[0]}'?" if matches else ""
        raise AttributeError(
            f"Struct has no field '{name}'.{hint} Valid fields: {', '.join(fields)}"
        )

    def __repr__(self) -> str:
        parts: list[str] = []
        for k in self._fields:
            v = getattr(self, k)
            if isinstance(v, int) and k.endswith("_ptr"):
                parts.append(f"{k}=0x{v:08X}")
            else:
                parts.append(f"{k}={v!r}")
        return f"Struct({', '.join(parts)})"
