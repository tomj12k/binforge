from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from binforge.core.engine import BinaryBuffer
from binforge.errors import DriverNotFoundError
from binforge.registry import _registry, register  # noqa: F401

if TYPE_CHECKING:
    from binforge.drivers.base import FormatDriver


def open(path: str | Path) -> FormatDriver:
    from binforge.drivers.base import FormatDriver  # avoid circular at module level

    # Importing drivers triggers @register side-effects
    try:
        import binforge.drivers.gba.fe6  # noqa: F401
    except ImportError:
        pass
    try:
        import binforge.drivers.gba.fe7  # noqa: F401
    except ImportError:
        pass
    try:
        import binforge.drivers.gba.fe8  # noqa: F401
    except ImportError:
        pass
    try:
        import binforge.drivers.snes.fe4  # noqa: F401
    except ImportError:
        pass
    try:
        import binforge.drivers.snes.fe5  # noqa: F401
    except ImportError:
        pass
    try:
        import binforge.drivers.n3ds.fe13  # noqa: F401
    except ImportError:
        pass
    try:
        import binforge.drivers.n3ds.fe14  # noqa: F401
    except ImportError:
        pass
    try:
        import binforge.drivers.n3ds.fe15  # noqa: F401
    except ImportError:
        pass

    buf = BinaryBuffer(path)
    for driver_cls in _registry:
        instance: FormatDriver = driver_cls(buf)
        if instance.detect(buf):
            return instance
    raise DriverNotFoundError(str(path))
