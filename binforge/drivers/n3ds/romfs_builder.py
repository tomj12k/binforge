"""Nintendo IVFC Level 3 ROMFS container builder."""
from __future__ import annotations

from binforge.errors import RomFSBuildError


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

    def _build_tree(self, files: dict[str, bytes | None]) -> object:
        raise NotImplementedError

    def _serialise(self, tree: object) -> bytes:
        raise NotImplementedError
