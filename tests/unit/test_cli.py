"""Tests for binforge.cli.main."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from binforge.cli.main import cli
from binforge.core.struct_types import Struct
from binforge.errors import DriverNotFoundError, TableNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver(table_data: list[Struct] | None = None) -> MagicMock:
    """Return a mock FormatDriver with sensible defaults."""
    drv = MagicMock()
    drv.ENDIAN = "little"
    drv.POINTER_BASE = 0x08000000
    drv.table_names.return_value = ["chars", "items"]
    if table_data is None:
        table_data = [
            Struct(["id", "hp"], id=1, hp=20),
            Struct(["id", "hp"], id=2, hp=18),
        ]
    drv.parse_table.return_value = table_data
    return drv


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------


def test_detect_success(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(cli, ["detect", str(f)])
    assert result.exit_code == 0
    assert "MagicMock" in result.output
    assert "endian=little" in result.output
    assert "ptr_base=0x08000000" in result.output
    assert "chars" in result.output


def test_detect_no_driver(tmp_path: Path) -> None:
    f = tmp_path / "unknown.bin"
    f.write_bytes(b"\xff" * 16)
    runner = CliRunner()
    with patch("binforge.open", side_effect=DriverNotFoundError(str(f))):
        result = runner.invoke(cli, ["detect", str(f)])
    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# dump
# ---------------------------------------------------------------------------


def test_dump_json_stdout(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(cli, ["dump", str(f), "chars"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[1]["hp"] == 18


def test_dump_csv_stdout(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(cli, ["dump", str(f), "chars", "--format", "csv"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines[0] == "id,hp"
    assert lines[1] == "1,20"


def test_dump_json_to_file(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    out = tmp_path / "out.json"
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(cli, ["dump", str(f), "chars", "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert data[0]["id"] == 1


def test_dump_empty_table_csv(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    drv = _make_driver(table_data=[])
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(cli, ["dump", str(f), "chars", "--format", "csv"])
    assert result.exit_code == 0


def test_dump_table_not_found(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    drv = MagicMock()
    drv.parse_table.side_effect = TableNotFoundError("chars")
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(cli, ["dump", str(f), "chars"])
    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# patch
# ---------------------------------------------------------------------------


def test_patch_inline(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    out = tmp_path / "patched.bin"
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(
            cli,
            [
                "patch",
                str(f),
                "chars",
                "--row",
                "0",
                "--field",
                "hp",
                "--value",
                "30",
                "--out",
                str(out),
            ],
        )
    assert result.exit_code == 0
    assert "Written to" in result.output
    drv.pack_table.assert_called_once()
    drv.commit.assert_called_once_with(str(out))


def test_patch_from_file(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    out = tmp_path / "patched.bin"
    edits_file = tmp_path / "edits.json"
    edits_file.write_text(json.dumps([{"row": 0, "field": "hp", "value": 25}]))
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(
            cli,
            ["patch", str(f), "chars", "--from-file", str(edits_file), "--out", str(out)],
        )
    assert result.exit_code == 0
    assert "Written to" in result.output


def test_patch_missing_args(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    out = tmp_path / "patched.bin"
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(cli, ["patch", str(f), "chars", "--out", str(out)])
    assert result.exit_code == 1


def test_patch_bad_row_index(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    out = tmp_path / "patched.bin"
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(
            cli,
            [
                "patch",
                str(f),
                "chars",
                "--row",
                "999",
                "--field",
                "hp",
                "--value",
                "1",
                "--out",
                str(out),
            ],
        )
    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# repack
# ---------------------------------------------------------------------------


def test_repack_delegates_to_patch(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    out = tmp_path / "repacked.bin"
    edits_file = tmp_path / "edits.json"
    edits_file.write_text(json.dumps([{"row": 0, "field": "hp", "value": 99}]))
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(
            cli,
            ["repack", str(f), "chars", "--from-file", str(edits_file), "--out", str(out)],
        )
    assert result.exit_code == 0
    assert "Written to" in result.output


# ---------------------------------------------------------------------------
# hex
# ---------------------------------------------------------------------------


def test_hex_basic(tmp_path: Path) -> None:
    f = tmp_path / "raw.bin"
    f.write_bytes(bytes(range(32)))
    runner = CliRunner()
    result = runner.invoke(cli, ["hex", str(f), "0", "--length", "16"])
    assert result.exit_code == 0
    assert "00000000" in result.output
    assert "00 01 02 03 04 05 06 07  08 09 0a 0b 0c 0d 0e 0f" in result.output


def test_hex_accepts_hex_offset(tmp_path: Path) -> None:
    f = tmp_path / "raw.bin"
    f.write_bytes(b"\x00" * 0x10 + b"\xaa\xbb")
    runner = CliRunner()
    result = runner.invoke(cli, ["hex", str(f), "0x10", "--length", "2"])
    assert result.exit_code == 0
    assert "00000010" in result.output
    assert "aa bb" in result.output


def test_hex_rejects_bad_offset(tmp_path: Path) -> None:
    f = tmp_path / "raw.bin"
    f.write_bytes(b"\x00")
    runner = CliRunner()
    result = runner.invoke(cli, ["hex", str(f), "zebra"])
    assert result.exit_code != 0
    assert "not a valid integer" in result.output


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------


def test_find_prints_offsets(tmp_path: Path) -> None:
    f = tmp_path / "raw.bin"
    f.write_bytes(b"\x00\xaf\xee\x00\x00\xaf\xee\x00")
    runner = CliRunner()
    result = runner.invoke(cli, ["find", str(f), "AF EE 00"])
    assert result.exit_code == 0
    assert result.output.splitlines() == ["0x00000001", "0x00000005"]


def test_find_no_matches(tmp_path: Path) -> None:
    f = tmp_path / "raw.bin"
    f.write_bytes(b"\x00" * 8)
    runner = CliRunner()
    result = runner.invoke(cli, ["find", str(f), "ff ff"])
    assert result.exit_code == 0
    assert "no matches" in result.output


def test_find_respects_limit(tmp_path: Path) -> None:
    f = tmp_path / "raw.bin"
    f.write_bytes(b"\xaa" * 10)
    runner = CliRunner()
    result = runner.invoke(cli, ["find", str(f), "aa", "--limit", "3"])
    assert result.exit_code == 0
    assert len(result.output.splitlines()) == 3


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def test_diff_two_regions(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    data = bytearray(b"\x00" * 64)
    a.write_bytes(bytes(data))
    data[4] = 0xFF
    data[40] = 0xEE
    b.write_bytes(bytes(data))
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(a), str(b)])
    assert result.exit_code == 0
    assert "-- 0x00000004 (1 bytes)" in result.output
    assert "-- 0x00000028 (1 bytes)" in result.output


def test_diff_max_regions(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    data = bytearray(b"\x00" * 64)
    a.write_bytes(bytes(data))
    for off in (0, 16, 32, 48):
        data[off] = 0xFF
    b.write_bytes(bytes(data))
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(a), str(b), "--max-regions", "2"])
    assert result.exit_code == 0
    assert result.output.count("-- 0x") == 2
    assert "... 2 more regions" in result.output


def test_diff_identical_files(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"\x01\x02")
    b.write_bytes(b"\x01\x02")
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(a), str(b)])
    assert result.exit_code == 0
    assert "identical" in result.output


def test_diff_length_mismatch_note(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"\x00" * 8)
    b.write_bytes(b"\x00" * 8 + b"\xff" * 4)
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(a), str(b)])
    assert result.exit_code == 0
    assert "sizes differ (8 vs 12 bytes)" in result.output


# ---------------------------------------------------------------------------
# dump --format table
# ---------------------------------------------------------------------------


def test_dump_table_format(tmp_path: Path) -> None:
    f = tmp_path / "game.bin"
    f.write_bytes(b"\x00" * 16)
    drv = _make_driver()
    runner = CliRunner()
    with patch("binforge.open", return_value=drv):
        result = runner.invoke(cli, ["dump", str(f), "chars", "--format", "table"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0].split() == ["id", "hp"]
    assert lines[1].split() == ["1", "20"]
