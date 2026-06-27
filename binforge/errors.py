"""Binforge exception types."""


class BinforgeError(Exception):
    """Base exception for all binforge errors."""

    pass


class DriverNotFoundError(BinforgeError):
    """Raised when no driver matches the given file."""

    def __init__(self, path: str) -> None:
        super().__init__(f"No driver matched: {path}")
        self.path = path


class PatchSizeError(BinforgeError):
    """Raised when a patch exceeds file bounds."""

    def __init__(self, offset: int, patch_len: int, file_size: int) -> None:
        super().__init__(
            f"Patch at 0x{offset:08X} ({patch_len} bytes) exceeds file size {file_size}"
        )


class PointerRangeError(BinforgeError):
    """Raised when a pointer resolves outside file bounds."""

    def __init__(self, addr: int, file_size: int) -> None:
        super().__init__(
            f"Pointer 0x{addr:08X} resolves outside file bounds ({file_size} bytes)"
        )


class DecompressionError(BinforgeError):
    """Raised when decompression fails."""

    def __init__(self, msg: str) -> None:
        super().__init__(f"Decompression failed: {msg}")


class TableNotFoundError(BinforgeError):
    """Raised when a named table cannot be found."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Table not found: '{name}'")


class CommitError(BinforgeError):
    """Raised when changes cannot be committed to a file."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Failed to commit to {path}: {reason}")
        self.path = path
