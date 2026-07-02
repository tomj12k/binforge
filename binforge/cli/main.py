from __future__ import annotations

import csv
import io
import json
import struct
import sys
from pathlib import Path

import click

import binforge
from binforge.core.engine import BinaryBuffer, diff_spans
from binforge.errors import BinforgeError
from binforge.repl.format import format_table
from binforge.repl.shell import launch as _repl_launch


def parse_int(
    ctx: click.Context | None, param: click.Parameter | None, value: str | None
) -> int | None:
    """Click callback: parse an integer in decimal or 0x-hex notation.

    :param ctx: Click context (unused)
    :param param: Click parameter (unused)
    :param value: Raw string value
    :returns: Parsed integer, or None if value is None
    :raises click.BadParameter: If value is not a valid integer
    """
    if value is None:
        return None
    try:
        return int(value, 0)
    except ValueError as e:
        raise click.BadParameter(f"not a valid integer: {value!r}") from e


@click.group()
def cli() -> None:
    """binforge — Fire Emblem binary file parser and editor."""


@cli.command(name="hex")
@click.argument("file", type=click.Path(exists=True))
@click.argument("offset", callback=parse_int)
@click.option("--length", callback=parse_int, default="256", help="Bytes to dump")
@click.option("--width", callback=parse_int, default="16", help="Bytes per line")
def hex_cmd(file: str, offset: int, length: int, width: int) -> None:
    """Hexdump FILE starting at OFFSET (decimal or 0x-hex)."""
    try:
        buf = BinaryBuffer(file)
        click.echo(buf.hexdump(offset, length, width))
    except (OSError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command(name="find")
@click.argument("file", type=click.Path(exists=True))
@click.argument("needle")
@click.option("--start", callback=parse_int, default="0", help="Search start offset")
@click.option("--limit", callback=parse_int, default="100", help="Max matches")
def find_cmd(file: str, needle: str, start: int, limit: int) -> None:
    """Find hex-string NEEDLE (e.g. "AF EE 00") in FILE."""
    try:
        buf = BinaryBuffer(file)
        offsets = buf.find(needle, start=start, limit=limit)
    except (OSError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not offsets:
        click.echo("no matches")
        return
    for off in offsets:
        click.echo(f"0x{off:08x}")


@cli.command(name="diff")
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
@click.option("--context", callback=parse_int, default="8", help="Context bytes")
@click.option("--max-regions", callback=parse_int, default="50", help="Region cap")
def diff_cmd(file_a: str, file_b: str, context: int, max_regions: int) -> None:
    """Byte-diff FILE_A against FILE_B, printing hexdumps of changed regions."""
    try:
        a = Path(file_a).read_bytes()
        b = Path(file_b).read_bytes()
    except OSError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if len(a) != len(b):
        click.echo(f"note: sizes differ ({len(a)} vs {len(b)} bytes); diffing common prefix only")

    regions = diff_spans(a, b)
    if not regions:
        click.echo("files identical" + (" (common prefix)" if len(a) != len(b) else ""))
        return

    buf_a = BinaryBuffer.from_bytes(a, name=file_a)
    buf_b = BinaryBuffer.from_bytes(b, name=file_b)
    for off, length in regions[:max_regions]:
        dump_off = max(0, off - context)
        dump_len = (off - dump_off) + length + context
        click.echo(f"-- 0x{off:08x} ({length} bytes)")
        click.echo(f"A: {file_a}")
        click.echo(buf_a.hexdump(dump_off, dump_len))
        click.echo(f"B: {file_b}")
        click.echo(buf_b.hexdump(dump_off, dump_len))
    if len(regions) > max_regions:
        click.echo(f"... {len(regions) - max_regions} more regions")


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
@click.option("--format", "fmt", type=click.Choice(["json", "csv", "table"]), default="json")
@click.option("--out", type=click.Path(), default=None)
def dump(file: str, table: str, fmt: str, out: str | None) -> None:
    """Dump TABLE from FILE as JSON, CSV, or an aligned text table."""
    try:
        drv = binforge.open(file)
        rows = drv.parse_table(table)
    except BinforgeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if fmt == "table":
        text = format_table(rows, limit=len(rows) or 1)
    elif fmt == "json":
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
