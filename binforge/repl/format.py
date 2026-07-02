"""Columnar pretty-printing of parsed Struct rows."""

from __future__ import annotations

from typing import Any

_MAX_CELL = 24


def _cell(value: Any) -> str:
    """Render a single cell value, truncating long strings.

    :param value: Field value from a Struct row
    :type value: Any
    :returns: Display string, at most ``_MAX_CELL`` characters
    :rtype: str
    """
    text = str(value)
    if len(text) > _MAX_CELL:
        text = text[: _MAX_CELL - 1] + "…"
    return text


def format_table(rows: list[Any], limit: int = 40) -> str:
    """Format a list of Struct rows as an aligned text table.

    The header comes from row 0's ``_fields``. Numeric values are
    right-aligned; everything else is left-aligned. Cell values longer
    than 24 characters are truncated. If ``rows`` exceeds ``limit``, a
    trailing ``... N more rows`` line is added.

    :param rows: Parsed Struct rows (each with ``_fields``)
    :type rows: list
    :param limit: Maximum number of rows to render
    :type limit: int
    :returns: Formatted table (no trailing newline), or ``"(no rows)"``
    :rtype: str
    """
    if not rows:
        return "(no rows)"
    fields = list(rows[0]._fields)
    shown = rows[:limit]
    grid = [[_cell(getattr(r, f)) for f in fields] for r in shown]
    numeric = [all(isinstance(getattr(r, f), (int, float)) for r in shown) for f in fields]
    widths = [max([len(fields[c])] + [len(g[c]) for g in grid]) for c in range(len(fields))]
    lines = ["  ".join(f"{fields[c]:<{widths[c]}}" for c in range(len(fields))).rstrip()]
    for row in grid:
        cells = [
            f"{row[c]:>{widths[c]}}" if numeric[c] else f"{row[c]:<{widths[c]}}"
            for c in range(len(fields))
        ]
        lines.append("  ".join(cells).rstrip())
    if len(rows) > limit:
        lines.append(f"... {len(rows) - limit} more rows")
    return "\n".join(lines)


def print_table(rows: list[Any], limit: int = 40) -> None:
    """Pretty-print a list of Struct rows as a columnar table.

    :param rows: Parsed Struct rows (each with ``_fields``)
    :type rows: list
    :param limit: Maximum number of rows to render
    :type limit: int
    """
    print(format_table(rows, limit=limit))
