"""Nintendo IVFC Level 3 ROMFS container builder."""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass, field as dc_field

from binforge.errors import RomFSBuildError

_SENTINEL = 0xFFFF_FFFF


@dataclass
class _FileNode:
    name: str
    data: bytes


@dataclass
class _DirNode:
    name: str
    parent: _DirNode | None = None
    children: list[_DirNode] = dc_field(default_factory=list)
    files: list[_FileNode] = dc_field(default_factory=list)


def _align4(n: int) -> int:
    return (n + 3) & ~3


def _align16(n: int) -> int:
    return (n + 15) & ~15


def _bucket_count(entry_count: int) -> int:
    n = max(3, entry_count)
    p = 1
    while p < n:
        p <<= 1
    return p


class RomFSBuilder:
    """Build a valid IVFC-wrapped ROMFS blob from a virtual file dict.

    :param files: Mapping of virtual path → file bytes.
                  Pass ``None`` as a value to mark a file for deletion
                  (used when merging against an existing ROMFS).
                  Leading slashes are stripped; paths are normalised to
                  forward-slash separators.
    """

    def build(self, files: dict[str, bytes | None]) -> bytes:
        """Build and return the ROMFS blob.

        :param files: Virtual path → content mapping.
        :raises RomFSBuildError: On duplicate normalised paths, names longer
            than 255 UTF-16 chars, or region size overflow.
        """
        normalised = self._normalise(files)
        tree = self._build_tree(normalised)
        return self._serialise(tree)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _normalise(self, files: dict[str, bytes | None]) -> dict[str, bytes | None]:
        """Strip leading/trailing slashes and collapse repeated separators; detect duplicates."""
        result: dict[str, bytes | None] = {}
        for raw_path, data in files.items():
            norm = "/".join(p for p in raw_path.split("/") if p)
            if norm in result:
                raise RomFSBuildError(norm, "duplicate virtual path")
            result[norm] = data
        return result

    def _build_tree(self, files: dict[str, bytes | None]) -> _DirNode:
        """Walk path dict and build an in-memory directory tree."""
        root = _DirNode(name="")

        def get_or_create_dir(parts: list[str]) -> _DirNode:
            node = root
            for part in parts:
                for child in node.children:
                    if child.name == part:
                        node = child
                        break
                else:
                    new_dir = _DirNode(name=part, parent=node)
                    node.children.append(new_dir)
                    node = new_dir
            return node

        for path, data in files.items():
            if data is None:
                continue  # deletion — omit from tree
            parts = path.split("/")
            dir_parts, filename = parts[:-1], parts[-1]
            if len(filename.encode("utf-16-le")) > 255 * 2:
                raise RomFSBuildError(path, "filename exceeds 255 UTF-16 chars")
            parent_dir = get_or_create_dir(dir_parts)
            parent_dir.files.append(_FileNode(name=filename, data=data))

        return root

    def _serialise(self, root: _DirNode) -> bytes:
        """Serialise the tree to an IVFC-wrapped ROMFS blob.

        The Level 3 blob layout (all regions 16-byte aligned):

        +0x00  Header (0x2C bytes) — 11 × u32 offsets/sizes
        then   dir hash table | dir metadata | file hash table | file metadata | file data

        Dir metadata has a sentinel entry at offset 0 (0x18 bytes, empty name),
        followed by the root dir at offset 0x18, then remaining dirs in BFS order.
        This matches the ``RomFS`` reader's assumption that root is at offset 0x18.

        :param root: Root ``_DirNode`` produced by ``_build_tree``.
        :returns: IVFC-wrapped bytes ready for consumption by ``RomFS``.
        """
        # ── 1. Flatten nodes: BFS, root first ───────────────────────────────
        dir_nodes: list[_DirNode] = []
        file_nodes: list[tuple[_DirNode, _FileNode]] = []

        queue: list[_DirNode] = [root]
        while queue:
            node = queue.pop(0)
            dir_nodes.append(node)
            for f in node.files:
                file_nodes.append((node, f))
            queue.extend(node.children)

        # ── 2. Assign dir metadata offsets ──────────────────────────────────
        # A sentinel (0x18 bytes, empty name) occupies the first slot;
        # the root dir is placed at offset 0x18 so the RomFS reader can find
        # it at the fixed address 0x18.
        SENTINEL_SIZE = 0x18  # empty-name entry: 6 × u32, no name bytes
        dir_offsets: dict[int, int] = {}  # id(node) → byte offset in dir_meta
        off = SENTINEL_SIZE  # root starts after sentinel
        for d in dir_nodes:
            dir_offsets[id(d)] = off
            name_enc = d.name.encode("utf-16-le")
            off += 0x18 + _align4(len(name_enc))

        dir_meta_size = _align16(off)

        # ── 3. Assign file metadata offsets ─────────────────────────────────
        file_offsets: dict[int, int] = {}  # index → byte offset in file_meta
        off = 0
        for i, (_, f) in enumerate(file_nodes):
            file_offsets[i] = off
            name_enc = f.name.encode("utf-16-le")
            off += 0x20 + _align4(len(name_enc))

        file_meta_size = _align16(off)

        # ── 4. Assign file data offsets ──────────────────────────────────────
        file_data_offsets: list[int] = []
        data_off = 0
        for _, f in file_nodes:
            file_data_offsets.append(data_off)
            data_off += _align16(len(f.data))
        file_data_total = data_off

        # ── 5. Hash table bucket counts ──────────────────────────────────────
        dir_bucket_count = _bucket_count(len(dir_nodes))
        file_bucket_count = _bucket_count(len(file_nodes))
        dir_hash_size = dir_bucket_count * 4
        file_hash_size = file_bucket_count * 4

        # ── 6. Compute region offsets (relative to start of Level 3) ────────
        header_size = 0x2C  # 11 × u32: magic + 5 × (offset, size) pairs
        dir_hash_off = header_size
        dir_meta_off = _align16(dir_hash_off + dir_hash_size)
        file_hash_off = _align16(dir_meta_off + dir_meta_size)
        file_meta_off = _align16(file_hash_off + file_hash_size)
        file_data_off = _align16(file_meta_off + file_meta_size)
        total_size = _align16(file_data_off + file_data_total)

        buf = bytearray(total_size)

        # ── 7. Level 3 header ────────────────────────────────────────────────
        # Actual layout (11 × u32 = 0x2C bytes):
        #   +0x00  magic / version (0x10000 — written but not checked by reader)
        #   +0x04  dir_hash_off   ← reader reads here
        #   +0x08  dir_hash_size
        #   +0x0C  dir_meta_off   ← reader reads here
        #   +0x10  dir_meta_size
        #   +0x14  file_hash_off  ← reader reads here
        #   +0x18  file_hash_size
        #   +0x1C  file_meta_off  ← reader reads here
        #   +0x20  file_meta_size
        #   +0x24  file_data_off  ← reader reads here
        #   +0x28  file_data_size (0 / unused)
        struct.pack_into(
            "<11I",
            buf,
            0,
            0x10000,        # magic
            dir_hash_off,
            dir_hash_size,
            dir_meta_off,
            dir_meta_size,
            file_hash_off,
            file_hash_size,
            file_meta_off,
            file_meta_size,
            file_data_off,
            0,              # file_data_size — unused by reader
        )

        # ── 8. Dir hash table (initialise to SENTINEL) ───────────────────────
        dht_base = dir_hash_off
        for bi in range(dir_bucket_count):
            struct.pack_into("<I", buf, dht_base + bi * 4, _SENTINEL)

        # Compute hash chains (not used by the linear-scan reader, but correct)
        dir_hash_next: list[int] = [_SENTINEL] * len(dir_nodes)
        for di, d in enumerate(dir_nodes):
            name_enc = d.name.encode("utf-16-le")
            bucket = zlib.crc32(name_enc) % dir_bucket_count
            cur = struct.unpack_from("<I", buf, dht_base + bucket * 4)[0]
            dir_hash_next[di] = cur
            struct.pack_into("<I", buf, dht_base + bucket * 4, dir_offsets[id(d)])

        # ── 9. Dir metadata ──────────────────────────────────────────────────
        # Sentinel at offset 0: all-SENTINEL fields, empty name.
        # Actual layout that the RomFS reader depends on:
        #   +0x00 parent_offset (u32)
        #   +0x04 sibling_offset (u32)      ← reader ignores this field
        #   +0x08 child_dir_offset (u32)    ← reader reads to descend
        #   +0x0C file_offset (u32)         ← reader reads to list files
        #   +0x10 sibling_next (u32)        ← reader uses to walk siblings
        #   +0x14 name_len (u32)
        #   +0x18 name (UTF-16-LE, 4-byte padded)
        dms_base = dir_meta_off

        # Write sentinel (6 × SENTINEL, no name bytes = 0x18 bytes total)
        for field_off in range(0, 0x18, 4):
            struct.pack_into("<I", buf, dms_base + field_off, _SENTINEL)

        for di, d in enumerate(dir_nodes):
            entry_off = dms_base + dir_offsets[id(d)]
            parent_off = dir_offsets[id(d.parent)] if d.parent else _SENTINEL
            # sibling: next child of the same parent (field +0x04, reader ignores)
            if d.parent:
                siblings = d.parent.children
                idx = siblings.index(d)
                sibling_off = (
                    dir_offsets[id(siblings[idx + 1])]
                    if idx + 1 < len(siblings)
                    else _SENTINEL
                )
            else:
                sibling_off = _SENTINEL
            child_off = dir_offsets[id(d.children[0])] if d.children else _SENTINEL
            first_file_idx = next(
                (i for i, (fd, _) in enumerate(file_nodes) if fd is d), None
            )
            first_file_off = (
                file_offsets[first_file_idx]
                if first_file_idx is not None
                else _SENTINEL
            )
            # sibling_next at +0x10: used by reader to walk sibling dirs
            # We store the same value as sibling_off so both fields are correct.
            name_enc = d.name.encode("utf-16-le")
            struct.pack_into("<I", buf, entry_off + 0x00, parent_off)
            struct.pack_into("<I", buf, entry_off + 0x04, sibling_off)
            struct.pack_into("<I", buf, entry_off + 0x08, child_off)
            struct.pack_into("<I", buf, entry_off + 0x0C, first_file_off)
            struct.pack_into("<I", buf, entry_off + 0x10, sibling_off)  # sibling_next
            struct.pack_into("<I", buf, entry_off + 0x14, len(name_enc))
            buf[entry_off + 0x18 : entry_off + 0x18 + len(name_enc)] = name_enc

        # ── 10. File hash table ──────────────────────────────────────────────
        fht_base = file_hash_off
        for bi in range(file_bucket_count):
            struct.pack_into("<I", buf, fht_base + bi * 4, _SENTINEL)

        file_hash_next: list[int] = [_SENTINEL] * len(file_nodes)
        for fi, (_, f) in enumerate(file_nodes):
            name_enc = f.name.encode("utf-16-le")
            bucket = zlib.crc32(name_enc) % file_bucket_count
            cur = struct.unpack_from("<I", buf, fht_base + bucket * 4)[0]
            file_hash_next[fi] = cur
            struct.pack_into("<I", buf, fht_base + bucket * 4, file_offsets[fi])

        # ── 11. File metadata ────────────────────────────────────────────────
        # Layout the reader uses:
        #   +0x00 parent_dir_offset (u32)
        #   +0x04 sibling_offset (u32)      ← reader ignores
        #   +0x08 data_offset (u64)
        #   +0x10 data_size (u64)
        #   +0x18 sibling_next (u32)        ← reader uses to walk files
        #   +0x1C name_len (u32)
        #   +0x20 name (UTF-16-LE, 4-byte padded)
        fms_base = file_meta_off
        for fi, (fd, f) in enumerate(file_nodes):
            entry_off = fms_base + file_offsets[fi]
            parent_off = dir_offsets[id(fd)]
            # sibling: next file in same dir
            dir_files = [i for i, (d2, _) in enumerate(file_nodes) if d2 is fd]
            my_pos = dir_files.index(fi)
            sibling_off = (
                file_offsets[dir_files[my_pos + 1]]
                if my_pos + 1 < len(dir_files)
                else _SENTINEL
            )
            name_enc = f.name.encode("utf-16-le")
            struct.pack_into("<I", buf, entry_off + 0x00, parent_off)
            struct.pack_into("<I", buf, entry_off + 0x04, sibling_off)
            struct.pack_into("<Q", buf, entry_off + 0x08, file_data_offsets[fi])
            struct.pack_into("<Q", buf, entry_off + 0x10, len(f.data))
            struct.pack_into("<I", buf, entry_off + 0x18, sibling_off)  # sibling_next
            struct.pack_into("<I", buf, entry_off + 0x1C, len(name_enc))
            buf[entry_off + 0x20 : entry_off + 0x20 + len(name_enc)] = name_enc

        # ── 12. File data ────────────────────────────────────────────────────
        for fi, (_, f) in enumerate(file_nodes):
            abs_off = file_data_off + file_data_offsets[fi]
            buf[abs_off : abs_off + len(f.data)] = f.data

        # ── 13. IVFC wrapper ─────────────────────────────────────────────────
        # The RomFS reader computes: l3_offset = 0x60 + master_hash_size.
        # master_hash_size is read from IVFC header offset 0x08.
        # We write master_hash_size = 0x20 (SHA-256), so l3_offset = 0x80.
        # Level 3 data is appended immediately after the 0x80-byte IVFC header.
        level3 = bytes(buf)
        master_hash = hashlib.sha256(level3).digest()  # 0x20 bytes

        ivfc = bytearray(0x80)
        struct.pack_into("<4sII", ivfc, 0x00, b"IVFC", 0x10000, 0x20)
        # Level 3 descriptor at offset 0x0C + 2×24 = 0x3C
        lvl3_desc = 0x0C + 2 * 24
        struct.pack_into(
            "<QQI",
            ivfc,
            lvl3_desc,
            0x80,           # level3_offset: immediately after IVFC header
            len(level3),    # level3_size
            0x0C,           # block_size (4 KB)
        )
        # Master hash at 0x60
        ivfc[0x60:0x80] = master_hash

        return bytes(ivfc) + level3
