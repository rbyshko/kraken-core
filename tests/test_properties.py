from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

from kraken.core.system.property import Object, Property


def test__Property_value_adapter_order_is_semantically_revelant() -> None:
    """Tests that a `str | Path` and `Path | str` property behave differently."""

    prop1: Property[Union[str, Path]] = Property(Object(), "prop1", Union[str, Path])
    prop1.set("foo/bar")
    assert prop1.get() == "foo/bar"

    prop2: Property[Union[Path, str]] = Property(Object(), "prop2", Union[Path, str])
    prop2.set("foo/bar")
    assert prop2.get() == Path("foo/bar")

    prop2.setmap(lambda s: Path(str(s).upper()))
    assert prop2.get() == Path("FOO/BAR")


def test__Property_default() -> None:
    """Tests that property defaults work as expected."""

    a_value = ["abc"]

    class MyObj(Object):
        a: Property[List[str]] = Property.config(default=a_value)
        b: Property[int] = Property.config(default_factory=lambda: 42)
        c: Property[str]

    obj = MyObj()
    assert obj.a.get() == a_value
    assert obj.a.get() is not a_value  # Copied
    assert obj.b.get() == 42
    assert obj.c.is_empty()


def test__Property_default_factory_with_subclass() -> None:
    """Tests that property default factory works with a subclass (a known previous semantic failure case)."""

    class MyObj(Object):
        b: Property[Dict[str, str]] = Property.default_factory(dict)

    class SubObj(MyObj):
        pass

    obj = MyObj()
    assert obj.b.get() == {}

    subobj = SubObj()
    assert subobj.b.get() == {}


def test__Property__provides() -> None:
    assert Property[str](Object(), "foo", str).provides(str)
    assert not Property[Path](Object(), "foo", Path).provides(str)
    assert Property[Union[str, Path]](Object(), "foo", Union[str, Path]).provides(str)
    assert Property[Union[str, Path]](Object(), "foo", Union[str, Path]).provides(Path)
    assert not Property[Union[str, Path]](Object(), "foo", Union[str, Path]).provides(int)
    assert not Property[Union[str, Path]](Object(), "foo", Union[str, Path]).provides(type(None))
    assert Property[Optional[str]](Object(), "foo", Optional[str]).provides(str)
    assert Property[Optional[str]](Object(), "foo", Optional[str]).provides(type(None))


def test__Property__get_of_type__scalar() -> None:
    p1 = Property[str](Object(), "foo", str)
    p1.set("bar")
    assert p1.get_of_type(str) == ["bar"]


def test__Property__get_of_type__scalar_no_match() -> None:
    p1 = Property[str](Object(), "foo", str)
    p1.set("bar")
    assert p1.get_of_type(int) == []


def test__Property__get_of_type__sequence() -> None:
    p1 = Property[List[str]](Object(), "foo", List[str])
    p1.set(["hello", "world"])
    assert p1.get_of_type(str) == ["hello", "world"]


def test__Property__get_of_type__sequence_no_match() -> None:
    p1 = Property[List[str]](Object(), "foo", List[str])
    p1.set(["hello", "world"])
    assert p1.get_of_type(int) == []


def test__Property__get_of_type__sequence_partial_match() -> None:
    p1 = Property[List[Union[str, int]]](Object(), "foo", List[Union[str, int]])
    p1.set(["hello", 42, "world"])
    assert p1.get_of_type(int) == [42]
    assert p1.get_of_type(str) == ["hello", "world"]
    assert p1.get_of_type(object) == ["hello", 42, "world"]
    assert p1.get_of_type(type(None)) == []
    assert p1.get_of_type(list) == [["hello", 42, "world"]]
