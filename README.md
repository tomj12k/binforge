# binforge

Round-trip binary editing for Fire Emblem ROMs — parse, modify, and repack character, class, item, and chapter data across GBA, SNES, and Nintendo 3DS eras.

## Supported Games

| Game | Era | Endian | Tables | Write |
|------|-----|--------|--------|-------|
| FE4 — Genealogy of the Holy War | SNES | big | characters, classes | ✅ |
| FE5 — Thracia 776 | SNES | big | characters | ✅ |
| FE6 — Binding Blade | GBA | little | characters, classes, items | ✅ |
| FE7 — Blazing Blade | GBA | little | characters, classes, items, weapons, skills, chapters | ✅ |
| FE8 — The Sacred Stones | GBA | little | characters, classes, items, skills, chapters | ✅ |
| FE13 — Awakening | 3DS | little | characters, classes | ✅ |
| FE14 — Fates | 3DS | little | characters, classes | ✅ |
| FE15 — Echoes: Shadows of Valentia | 3DS | little | characters, classes | ✅ |

## Install

```bash
uv sync
uv run binforge --help
```

## CLI Quickstart

```bash
# Identify a ROM
uv run binforge detect fe7.gba
# → Detected: FE7Driver (little-endian, GBA, pointer base 0x08000000)
# → Tables: characters, classes, items, weapons, skills, chapters

# Dump the characters table to JSON
uv run binforge dump fe7.gba characters --format json --out chars.json

# Patch Lyn's HP (row 0) to 99
uv run binforge patch fe7.gba characters --row 0 --field hp --value 99 --out fe7_patched.gba

# Bulk patch from a JSON edits file
uv run binforge patch fe7.gba characters --from-file edits.json --out fe7_patched.gba
```

## Exploring

```bash
# Hexdump 256 bytes at an offset (hex or decimal)
uv run binforge hex fe7.gba 0xBDCE18 --length 64

# Find a byte pattern (hex string, quote it)
uv run binforge find fe7.gba "12 00 04 09" --limit 10

# Byte-diff two ROMs, hexdumps of each changed region
uv run binforge diff fe7.gba fe7_patched.gba --context 8
```

The REPL preloads exploration helpers (`buf`, `hexdump`, `find`, `deref`, `view`, `dirty`, `print_table`):

```python
>>> hexdump(0xBDCE18, 32)              # classic hexdump at a file offset
>>> find("12 00 04 09")                # → [12439064, ...]
>>> deref(0x08BDCE18, 32)              # follow a pointer, dump + text preview
>>> rows = view(0x08BDCE18, 16, 4)     # ad-hoc 16-byte-row table hypothesis
>>> print_table(rows)                  # aligned columnar print
>>> dirty()                            # 0x00bdce18 +2, or "clean"
```

## REPL Quickstart

```bash
uv run binforge shell fe7.gba
```

```python
>>> rom.table_names()
['characters', 'classes', 'items', 'weapons', 'skills', 'chapters']

>>> chars = rom.parse_table("characters")
>>> chars[0]
Struct(name_ptr='Lyn', hp=20, str=4, skl=9, spd=12, lck=14, def_=4, res=0)

>>> chars[0].hp = 99
>>> rom.pack_table("characters", chars)
>>> rom.commit("fe7_patched.gba")
```

## Writing a Driver

```python
from binforge.core.struct_types import Field, TableDef, u8, u32
from binforge.core.engine import BinaryBuffer
from binforge.drivers.base import FormatDriver
from binforge.registry import register

@register
class MyDriver(FormatDriver):
    MAGIC = b"MY GAME\x00"
    ENDIAN = "little"
    POINTER_BASE = 0x08000000

    def detect(self, buf: BinaryBuffer) -> bool:
        return buf.read_bytes(0xAC, 4) == b"MYID"

    def tables(self) -> dict[str, TableDef]:
        return {
            "units": TableDef(offset=0x08010000, row_size=16, count=64, fields=[
                Field("hp", u8, 0x00),
                Field("atk", u8, 0x01),
            ]),
        }
```

## Limitations

- Table offsets are community-documented and unverified against real ROMs — treat as best-effort until confirmed against a real cart dump.
- FE5 (Thracia 776) title detection is based on the documented SNES header; needs confirmation against a real cart dump.
- GBA text encoding (character names) is implemented for FE6/7/8 only. SNES and 3DS name fields remain raw pointers.
- 3DS ROMFS repacking is implemented but untested against real ROMs — extract your ROMFS with ctrtool and back up before use.
- `compress_lz11` is literal-only (valid but large). LZ10 uses a full sliding-window compressor.
