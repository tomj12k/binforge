from __future__ import annotations

import csv
import io
import json
import struct
import sys
from pathlib import Path

import click

import binforge
from binforge.errors import BinforgeError
from binforge.repl.shell import launch as _repl_launch


@click.group()
def cli() -> None:
    """binforge — Fire Emblem binary file parser and editor."""


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def detect(file: str) -> None:
    """Identify which driver handles FILE."""
    try:
        drv = binforge.open(file)
    except BinforgeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(
        f"Detected: {type(drv).__name__}  endian={drv.ENDIAN}  ptr_base=0x{drv.POINTER_BASE:08X}"
    )
    click.echo(f"Tables: {', '.join(drv.table_names())}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("table")
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json")
@click.option("--out", type=click.Path(), default=None)
def dump(file: str, table: str, fmt: str, out: str | None) -> None:
    """Dump TABLE from FILE as JSON or CSV."""
    try:
        drv = binforge.open(file)
        rows = drv.parse_table(table)
    except BinforgeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if fmt == "json":
        data = [{f: getattr(r, f) for f in r._fields} for r in rows]
        text = json.dumps(data, indent=2)
    else:
        if not rows:
            text = ""
        else:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=rows[0]._fields)
            writer.writeheader()
            for r in rows:
                writer.writerow({f: getattr(r, f) for f in r._fields})
            text = buf.getvalue()

    if out:
        Path(out).write_text(text)
        click.echo(f"Written to {out}")
    else:
        click.echo(text)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("table")
@click.option("--row", "row_idx", type=int, default=None, help="Row index (0-based)")
@click.option("--field", default=None, help="Field name")
@click.option("--value", default=None, help="New value (integer or string)")
@click.option(
    "--from-file",
    "from_file",
    type=click.Path(exists=True),
    default=None,
    help="JSON file: list of {row, field, value} dicts",
)
@click.option("--out", type=click.Path(), required=True)
def patch(
    file: str,
    table: str,
    row_idx: int | None,
    field: str | None,
    value: str | None,
    from_file: str | None,
    out: str,
) -> None:
    """Patch TABLE in FILE and write result to --out."""
    try:
        drv = binforge.open(file)
        rows = drv.parse_table(table)
    except BinforgeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if from_file:
        edits = json.loads(Path(from_file).read_text())
        try:
            for edit in edits:
                r, f, v = edit["row"], edit["field"], edit["value"]
                cur = getattr(rows[r], f)
                setattr(rows[r], f, type(cur)(v))
        except (KeyError, IndexError, AttributeError, ValueError) as e:
            click.echo(f"Error applying edits: {e}", err=True)
            sys.exit(1)
    elif row_idx is not None and field and value is not None:
        try:
            cur = getattr(rows[row_idx], field)
            setattr(rows[row_idx], field, type(cur)(value))
        except (IndexError, AttributeError, ValueError) as e:
            click.echo(f"Error applying patch: {e}", err=True)
            sys.exit(1)
    else:
        click.echo("Provide --row/--field/--value or --from-file", err=True)
        sys.exit(1)

    try:
        drv.pack_table(table, rows)
        drv.commit(out)
        click.echo(f"Written to {out}")
    except (BinforgeError, struct.error) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("table")
@click.option(
    "--from-file",
    "from_file",
    type=click.Path(exists=True),
    required=True,
)
@click.option("--out", type=click.Path(), required=True)
def repack(file: str, table: str, from_file: str, out: str) -> None:
    """Decompress, patch TABLE, recompress, write to --out. (3DS drivers only)"""
    patch.callback(  # type: ignore[attr-defined]
        file=file,
        table=table,
        row_idx=None,
        field=None,
        value=None,
        from_file=from_file,
        out=out,
    )


@cli.command(name="shell")
@click.argument("file", type=click.Path(exists=True))
def shell_cmd(file: str) -> None:
    """Open FILE in an interactive REPL with the ROM pre-loaded as `rom`."""
    _repl_launch(file)
