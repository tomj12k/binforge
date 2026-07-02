from __future__ import annotations

from typing import Any

import click

import binforge
from binforge.errors import DriverNotFoundError
from binforge.repl.format import print_table


def _build_namespace(rom: Any, path: str = "<memory>") -> tuple[dict[str, Any], str]:
    """Build the REPL namespace and banner for a loaded driver.

    :param rom: A FormatDriver instance
    :type rom: FormatDriver
    :param path: Display path of the loaded file, used in the banner
    :type path: str
    :returns: (namespace dict, banner string)
    :rtype: tuple[dict, str]
    """
    buf = rom._buf

    def hexdump(offset: int, length: int = 256) -> None:
        """Print a hexdump of the buffer at offset."""
        print(buf.hexdump(offset, length))

    def find(needle: bytes | str, start: int = 0) -> list[int]:
        """Return offsets of a byte/hex-string pattern."""
        return buf.find(needle, start)

    def deref(ptr: int, length: int = 64) -> None:
        """Print a hexdump (and text preview) of a pointer target."""
        print(rom.deref(ptr, length))

    def view(offset: int, row_size: int, count: int, fields: Any = None) -> list[Any]:
        """Parse an ad-hoc table for hypothesis testing."""
        return rom.view(offset, row_size, count, fields)

    def dirty() -> None:
        """Print dirty ranges as '0x{offset:08x} +{length}' lines, or 'clean'."""
        spans = buf.dirty_ranges()
        if not spans:
            print("clean")
            return
        for off, length in spans:
            print(f"0x{off:08x} +{length}")

    banner = (
        f"\nbinforge shell — {type(rom).__name__}\n"
        f"  file   : {path}\n"
        f"  tables : {', '.join(rom.table_names())}\n\n"
        f"  rom.parse_table('characters')   → list of Struct\n"
        f"  rom.pack_table('characters', rows)\n"
        f"  rom.commit('output.gba')\n\n"
        f"  helpers:\n"
        f"    buf                              underlying BinaryBuffer\n"
        f"    hexdump(offset, length=256)      print hexdump at offset\n"
        f"    find(needle, start=0)            offsets of hex-string/bytes pattern\n"
        f"    deref(ptr, length=64)            print pointer target hexdump + text\n"
        f"    view(offset, row_size, count, fields=None)  ad-hoc table parse\n"
        f"    dirty()                          print dirty ranges, or 'clean'\n"
        f"    print_table(rows, limit=40)      columnar print of Struct rows\n"
    )

    namespace: dict[str, Any] = {
        "rom": rom,
        "buf": buf,
        "binforge": binforge,
        "hexdump": hexdump,
        "find": find,
        "deref": deref,
        "view": view,
        "dirty": dirty,
        "print_table": print_table,
    }
    return namespace, banner


def launch(path: str) -> None:
    """Open FILE in an IPython REPL with the ROM pre-loaded as `rom`."""
    try:
        rom = binforge.open(path)
    except DriverNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        return

    namespace, banner = _build_namespace(rom, path)

    try:
        import IPython

        IPython.embed(
            header=banner,
            user_ns=namespace,
            colors="neutral",
        )
    except ImportError:
        import code

        code.interact(banner=banner, local=namespace)
