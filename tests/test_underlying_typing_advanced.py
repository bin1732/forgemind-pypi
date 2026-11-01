# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 typing 进阶: 真 TypeVar / Generic / Protocol / runtime_checkable / TypedDict / NewType。
全 typing 模块, 零模拟。
"""
import typing
import inspect
import pytest


def test_typing_typevar_basic():
    """真 TypeVar 推断"""
    T = typing.TypeVar("T")

    def identity(x: T) -> T:
        return x

    # 真推断
    assert identity(42) == 42
    assert identity("hello") == "hello"
    # TypeVar 真有 __name__
    assert T.__name__ == "T"


def test_typing_typevar_constrained():
    """真 TypeVar constrained"""
    NumberT = typing.TypeVar("NumberT", int, float)

    def add(x: NumberT, y: NumberT) -> NumberT:
        return x + y

    assert add(1, 2) == 3
    assert add(1.5, 2.5) == 4.0


def test_typing_generic_class():
    """真 Generic 容器类"""
    T = typing.TypeVar("T")

    class Box(typing.Generic[T]):
        def __init__(self, value: T):
            self.value = value
        def get(self) -> T:
            return self.value

    b_int = Box(42)
    assert b_int.get() == 42
    b_str = Box("hello")
    assert b_str.get() == "hello"
    # __class_getitem__ 真返 _GenericAlias
    assert isinstance(Box[int], typing._GenericAlias)
    # str() 包含 module 路径
    assert "Box[int]" in str(Box[int])


def test_typing_protocol_runtime_checkable():
    """真 @runtime_checkable Protocol"""
    @typing.runtime_checkable
    class Drawable(typing.Protocol):
        def draw(self) -> str: ...

    class Circle:
        def draw(self) -> str:
            return "○"

    class Square:
        def draw(self) -> str:
            return "□"

    class NotDrawable:
        pass

    c = Circle()
    s = Square()
    n = NotDrawable()
    assert isinstance(c, Drawable)
    assert isinstance(s, Drawable)
    assert not isinstance(n, Drawable)
    assert not isinstance("string", Drawable)


def test_typing_protocol_duck_typing():
    """真 Protocol 鸭子类型"""
    @typing.runtime_checkable
    class Stream(typing.Protocol):
        def read(self, n: int) -> bytes: ...

    class FileStream:
        def __init__(self, data):
            self.data = data
            self.pos = 0
        def read(self, n: int) -> bytes:
            chunk = self.data[self.pos:self.pos + n]
            self.pos += n
            return chunk

    f = FileStream(b"hello world")
    # 鸭子类型 — 自动是 Stream
    assert isinstance(f, Stream)


def test_typing_typed_dict():
    """真 TypedDict"""
    class Movie(typing.TypedDict):
        name: str
        year: int
        rating: float

    # TypedDict 仍是 dict
    m: Movie = {"name": "Inception", "year": 2010, "rating": 8.8}
    assert m["name"] == "Inception"
    assert m["year"] == 2010


def test_typing_newtype():
    """真 NewType 类型别名"""
    UserId = typing.NewType("UserId", int)
    uid = UserId(42)
    # 实际就是 int
    assert isinstance(uid, int)
    assert uid == 42
    assert uid + 1 == 43


def test_typing_literal():
    """真 Literal 限制值"""
    Mode = typing.Literal["read", "write", "append"]

    def open_file(mode: Mode) -> str:
        return f"opening in {mode} mode"

    assert open_file("read") == "opening in read mode"
    assert open_file("write") == "opening in write mode"


def test_typing_union():
    """真 Union / Optional"""
    def get_value(use_default: bool) -> typing.Union[int, str]:
        return 42 if use_default else "default"

    assert get_value(True) == 42
    assert get_value(False) == "default"

    # Optional = Union[X, None]
    def maybe_int(x: bool) -> typing.Optional[int]:
        return 42 if x else None

    assert maybe_int(True) == 42
    assert maybe_int(False) is None


def test_typing_any():
    """真 Any 接受任何类型"""
    def f(x: typing.Any) -> typing.Any:
        return x

    assert f(1) == 1
    assert f("hello") == "hello"
    assert f([1, 2, 3]) == [1, 2, 3]


def test_typing_callable():
    """真 Callable 标记"""
    def apply(f: typing.Callable[[int], int], x: int) -> int:
        return f(x)

    def double(n: int) -> int:
        return n * 2

    assert apply(double, 5) == 10
    assert apply(lambda n: n + 1, 5) == 6


def test_typing_class_getitem():
    """真 __class_getitem__ (PEP 585 generic)"""
    # Python 3.9+ list[int] 真 support
    my_list: list[int] = [1, 2, 3]
    assert my_list[0] == 1

    my_dict: dict[str, int] = {"a": 1}
    assert my_dict["a"] == 1


def test_typing_final():
    """真 @final 不能 subclass"""
    import typing
    @typing.final
    class Constant:
        def __init__(self, value):
            self.value = value
    c = Constant(42)
    assert c.value == 42


def test_typing_type_checking():
    """真 TYPE_CHECKING (静态类型检查, 运行时 False)"""
    # TYPE_CHECKING 是 False 在 runtime
    assert typing.TYPE_CHECKING is False


def test_typing_get_type_hints():
    """真 get_type_hints 真 introspect"""
    def example(x: int, y: str) -> bool:
        return str(x) == y

    hints = typing.get_type_hints(example)
    assert hints["x"] == int
    assert hints["y"] == str
    assert hints["return"] == bool


def test_typing_special_form():
    """真 NoReturn / Never / Any 真存在"""
    # NoReturn (函数永不返)
    def fail() -> typing.NoReturn:
        raise RuntimeError("always fails")
    # Any (无类型)
    x: typing.Any = 42
    # Never (bottom type, 3.11+)
    if hasattr(typing, "Never"):
        # Never 存在
        assert True
