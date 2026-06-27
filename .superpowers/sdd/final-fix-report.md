# Final Fix Report

## Changes

### `binforge/core/text.py`
- `TextCodec.decode_bytes`: changed fallback from `""` to `"<U+FFFD>"` (`"<replacement char>"`) so unknown bytes produce the Unicode replacement character instead of being silently dropped.
- Docstring already accurately described this behavior (was pre-existing), no change needed there.

### `binforge/drivers/gba/codec_fe6.py`
- `0x6D` (line-break): changed from `"\n"` to `` (U+E001, PUA).
- `0x80` (end-of-string): changed from `""` to `` (U+E080, PUA).

### `binforge/drivers/gba/codec_fe7.py`
- `0x6D` (line-break): changed from `"\n"` to `` (U+E001, PUA).
- `0x80` (end-of-string): was already U+E080; comment updated for clarity.

### `binforge/drivers/gba/codec_fe8.py`
- No direct edit required; imports `_TABLE` from `codec_fe7`, so PUA changes propagate automatically.

### `binforge/drivers/n3ds/romfs_builder.py`
- `_normalise()`: replaced `raw_path.lstrip("/")` with `"/".join(p for p in raw_path.split("/") if p)`, which collapses repeated `/` (e.g., `a//b.bin` → `a/b.bin`) and strips both leading and trailing slashes.
- `_serialise()` docstring: corrected "Header (0x28 bytes) — 10 × u32" to "Header (0x2C bytes) — 11 × u32".

### `tests/unit/test_text_codec.py`
- `_TABLE` entry for `0x04`: changed value from `""` to `` (U+E001).
- `test_control_code_roundtrip`: test string updated to use U+E001 between "A" and "B".

## Test Run

Command: `cd ~/binforge && uv run pytest -v`

Result: **117 passed** in 0.12s

## Lint

Command: `cd ~/binforge && uv run ruff check binforge/`

Result: All checks passed.
