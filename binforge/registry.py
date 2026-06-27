from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binforge.drivers.base import FormatDriver

_registry: list[type[FormatDriver]] = []


def register(cls: type[FormatDriver]) -> type[FormatDriver]:
    _registry.append(cls)
    return cls
