from binforge.registry import _registry, register
from binforge.drivers.base import FormatDriver
from binforge.core.engine import BinaryBuffer
from binforge.core.struct_types import TableDef


def test_register_adds_to_registry():
    initial = len(_registry)

    @register
    class _Dummy(FormatDriver):
        MAGIC = b"\xDD\xDD"
        def detect(self, buf: BinaryBuffer) -> bool:
            return False
        def tables(self) -> dict[str, TableDef]:
            return {}

    assert len(_registry) == initial + 1
    _registry.remove(_Dummy)  # clean up
