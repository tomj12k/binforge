from binforge.core.struct_types import (
    Field,
    Struct,
    TableDef,
    fixed_str,
    ptr,
    str_ptr,
    u8,
)


def test_u8_properties():
    assert u8.fmt == "B"
    assert u8.size == 1
    assert not u8.is_ptr
    assert not u8.is_str


def test_ptr_properties():
    assert ptr.size == 4
    assert ptr.is_ptr
    assert not ptr.is_str


def test_fixed_str():
    ft = fixed_str(8)
    assert ft.size == 8
    assert ft.is_str
    assert not ft.is_ptr


def test_field():
    f = Field("hp", u8, 0x04)
    assert f.name == "hp"
    assert f.ftype is u8
    assert f.offset == 0x04


def test_tabledef():
    tdef = TableDef(
        offset=0x0803A820,
        row_size=52,
        count=256,
        fields=[Field("hp", u8, 0x04)],
    )
    assert tdef.count == 256
    assert tdef.row_size == 52


def test_struct_attribute_access():
    s = Struct(["hp", "str"], hp=20, str=4)
    assert s.hp == 20
    assert s.str == 4


def test_struct_mutation():
    s = Struct(["hp"], hp=20)
    s.hp = 99
    assert s.hp == 99


def test_struct_repr_normal():
    s = Struct(["hp", "str"], hp=20, str=4)
    r = repr(s)
    assert "hp=20" in r
    assert "str=4" in r


def test_struct_repr_ptr_hex():
    s = Struct(["name_ptr"], name_ptr=0x0847A820)
    r = repr(s)
    assert "0x0847A820" in r


def test_str_ptr_is_str_ptr() -> None:
    assert str_ptr.is_str_ptr is True


def test_str_ptr_is_ptr() -> None:
    assert str_ptr.is_ptr is True


def test_str_ptr_size() -> None:
    assert str_ptr.size == 4


def test_struct_has_raw_dict() -> None:
    s = Struct(["name"], name="Lyn")
    assert hasattr(s, "_raw")
    assert isinstance(s._raw, dict)
