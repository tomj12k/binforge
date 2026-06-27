from binforge.errors import PointerRangeError


class PointerTable:
    def __init__(self, base: int, endian: str) -> None:
        self._base = base
        self._endian = endian

    def resolve(self, rom_addr: int) -> int:
        """ROM address → file byte offset."""
        return rom_addr - self._base

    def rebase(self, file_offset: int) -> int:
        """File byte offset → ROM address."""
        return file_offset + self._base

    def check_bounds(self, rom_addr: int, file_size: int) -> None:
        offset = self.resolve(rom_addr)
        if offset < 0 or offset >= file_size:
            raise PointerRangeError(rom_addr, file_size)
