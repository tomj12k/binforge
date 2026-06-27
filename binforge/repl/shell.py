from __future__ import annotations

import click

import binforge
from binforge.errors import DriverNotFoundError


def launch(path: str) -> None:
    """Open FILE in an IPython REPL with the ROM pre-loaded as `rom`."""
    try:
        rom = binforge.open(path)
    except DriverNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        return

    driver_name = type(rom).__name__
    banner = (
        f"\nbinforge shell — {driver_name}\n"
        f"  file   : {path}\n"
        f"  tables : {', '.join(rom.table_names())}\n\n"
        f"  rom.parse_table('characters')   → list of Struct\n"
        f"  rom.pack_table('characters', rows)\n"
        f"  rom.commit('output.gba')\n"
    )

    try:
        import IPython

        IPython.embed(
            header=banner,
            user_ns={"rom": rom, "binforge": binforge},
            colors="neutral",
        )
    except ImportError:
        import code

        code.interact(banner=banner, local={"rom": rom, "binforge": binforge})
