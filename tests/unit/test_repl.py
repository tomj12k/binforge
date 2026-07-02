"""Tests for binforge.repl.shell namespace and binforge.repl.format."""

from __future__ import annotations

import struct

from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import Field, TableDef, u8, u16
from binforge.core.struct_types import Struct
from binforge.drivers.base import FormatDriver
from binforge.repl.format import format_table, print_table
from binforge.repl.shell import _build_namespace


class _ReplDriver(FormatDriver):
    MAGIC = b"\xfe\xfe"
    ENDIAN = "little"
    POINTER_BASE = 0x00000000

    def detect(self, buf: BinaryBuffer) -> bool:
        return buf.read_u16(0) == 0xFEFE

    def tables(self) -> dict[str, TableDef]:
        return {
            "units": TableDef(
                offset=0,
                row_size=4,
                count=2,
                fields=[
                    Field("hp", u8, 0),
                    Field("str", u8, 1),
                    Field("id", u16, 2),
                ],
            )
        }


def _driver() -> _ReplDriver:
    data = struct.pack("<BBH", 20, 4, 1) + struct.pack("<BBH", 18, 6, 2)
    return _ReplDriver(BinaryBuffer.from_bytes(data))


# ---------------------------------------------------------------------------
# _build_namespace
# ---------------------------------------------------------------------------


def test_namespace_contains_all_helpers():
    ns, banner = _build_namespace(_driver(), "x.bin")
    for key in (
        "rom",
        "buf",
        "binforge",
        "hexdump",
        "find",
        "deref",
        "view",
        "dirty",
        "print_table",
    ):
        assert key in ns, key
    assert "x.bin" in banner
    for helper in ("hexdump", "find", "deref", "view", "dirty", "print_table"):
        assert helper in banner


def test_namespace_buf_is_underlying_buffer():
    drv = _driver()
    ns, _ = _build_namespace(drv)
    assert ns["buf"] is drv._buf


def test_dirty_helper_clean(capsys):
    ns, _ = _build_namespace(_driver())
    ns["dirty"]()
    assert capsys.readouterr().out.strip() == "clean"


def test_dirty_helper_reports_spans(capsys):
    drv = _driver()
    drv._buf.patch(1, b"\xff")
    ns, _ = _build_namespace(drv)
    ns["dirty"]()
    assert capsys.readouterr().out.strip() == "0x00000001 +1"


def test_hexdump_helper_prints(capsys):
    ns, _ = _build_namespace(_driver())
    ns["hexdump"](0, 8)
    assert "00000000" in capsys.readouterr().out


def test_find_helper_returns_offsets():
    ns, _ = _build_namespace(_driver())
    assert ns["find"]("14")[0] == 0  # 0x14 == 20 == hp of row 0


def test_view_helper_returns_rows():
    ns, _ = _build_namespace(_driver())
    rows = ns["view"](0, 4, 2)
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# format_table / print_table
# ---------------------------------------------------------------------------


def _rows() -> list[Struct]:
    return [
        Struct(["id", "hp", "name"], id=1, hp=20, name="Lyn"),
        Struct(["id", "hp", "name"], id=2, hp=180, name="Hector"),
    ]


def test_format_table_golden():
    out = format_table(_rows())
    assert out == ("id  hp   name\n 1   20  Lyn\n 2  180  Hector")


def test_format_table_truncates_long_cells():
    rows = [Struct(["name"], name="x" * 40)]
    out = format_table(rows)
    lines = out.splitlines()
    assert len(lines[1]) <= 24
    assert lines[1].endswith("…")


def test_format_table_limit():
    rows = [Struct(["id"], id=i) for i in range(10)]
    out = format_table(rows, limit=3)
    assert "... 7 more rows" in out
    assert out.count("\n") == 4  # header + 3 rows + more-line


def test_format_table_empty():
    assert format_table([]) == "(no rows)"


def test_print_table_prints(capsys):
    print_table(_rows())
    out = capsys.readouterr().out
    assert "Lyn" in out and "Hector" in out
