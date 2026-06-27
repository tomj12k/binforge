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
