"""Nintendo IVFC Level 3 ROMFS container builder."""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from binforge.errors import RomFSBuildError


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

    # ── helpers (stubs) ──────────────────────────────────────────────────

    def _normalise(self, files: dict[str, bytes | None]) -> dict[str, bytes | None]:
        """Strip leading slashes; detect duplicates after normalisation."""
        result: dict[str, bytes | None] = {}
        for raw_path, data in files.items():
            norm = raw_path.lstrip("/")
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

    def _serialise(self, tree: object) -> bytes:
        raise NotImplementedError
