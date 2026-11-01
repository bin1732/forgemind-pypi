# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""collections.abc 方向的底层真实行为测试:抽象基类判定边界与子类钩子机制。

覆盖模块:collections.abc(标准库抽象基类集合)。

真实测试项:
  - `Sequence` 的 isinstance 判定真只认注册进来的序列类型
  - `Mapping` 的 isinstance 判定真只认映射类型,键值对列表不算
  - `Set` 的 isinstance 判定真只认集合类型,且区分可变与不可变
  - `Callable` 的 isinstance 判定真只认可调用对象
  - `Sequence` 在 3.11 没有结构化 `__subclasshook__`,真返回 NotImplemented
  - `Iterable` / `Iterator` 的 `__subclasshook__` 真按 `__iter__` / `__next__` 判定
  - `Sized` / `Container` 的 `__subclasshook__` 真按 `__len__` / `__contains__` 判定
  - `Collection` 的 `__subclasshook__` 真要求三个方法同时具备
  - `Callable` / `Hashable` / `Reversible` 的 `__subclasshook__` 真给出真实结果
  - `register` 真把普通类登记成虚拟子类
  - `abstractmethod` 真阻止实例化并点名未实现的抽象方法
  - `__abstractmethods__` 真列出尚未实现的抽象方法
  - 补齐抽象方法后 `__abstractmethods__` 真被清空
  - 抽象 classmethod 与抽象 property 真被记进 `__abstractmethods__`
"""

import abc
import collections
import collections.abc as cabc

import pytest


class _OnlyIter:
    """只实现 `__iter__` 的类。"""

    def __iter__(self):
        return iter(())


class _OnlyLen:
    """只实现 `__len__` 的类。"""

    def __len__(self):
        return 0


class _OnlyContains:
    """只实现 `__contains__` 的类。"""

    def __contains__(self, item):
        return False


class _OnlyReversed:
    """只实现 `__reversed__` 的类。"""

    def __reversed__(self):
        return iter(())


class _ReversedAndIter:
    """同时实现 `__reversed__` 与 `__iter__` 的类。"""

    def __reversed__(self):
        return iter(())

    def __iter__(self):
        return iter(())


class _OnlyCall:
    """只实现 `__call__` 的类。"""

    def __call__(self):
        return "called"


class _OnlyHash:
    """显式实现 `__hash__` 的类。"""

    def __hash__(self):
        return 1


class _Unhashable:
    """把 `__hash__` 置为 None 的类。"""

    __hash__ = None


class _IterAndNext:
    """同时实现 `__iter__` 与 `__next__` 的类。"""

    def __iter__(self):
        return iter(())

    def __next__(self):
        raise StopIteration


class _FullCollection:
    """同时实现 `__len__` / `__iter__` / `__contains__` 的类。"""

    def __len__(self):
        return 0

    def __iter__(self):
        return iter(())

    def __contains__(self, item):
        return False


class _StructuralSequence:
    """结构上像序列但没有注册进 ABC 的类。"""

    def __getitem__(self, index):
        raise IndexError

    def __len__(self):
        return 0


class _PartialSequence(cabc.Sequence):
    """只实现了 `__getitem__` 的抽象序列。"""

    @abc.abstractmethod
    def __getitem__(self, index):
        raise IndexError


def test_sequence_isinstance_accepts_registered_builtin_sequences() -> None:
    """`Sequence` 真只认注册进来的序列类型,映射与整数都不算序列。"""
    assert isinstance([1, 2], cabc.Sequence) is True
    assert isinstance((1, 2), cabc.Sequence) is True
    assert isinstance("ab", cabc.Sequence) is True
    assert isinstance(b"ab", cabc.Sequence) is True
    assert isinstance(range(3), cabc.Sequence) is True
    assert isinstance(memoryview(b"ab"), cabc.Sequence) is True
    assert isinstance({"a": 1}, cabc.Sequence) is False
    assert isinstance(5, cabc.Sequence) is False
    assert issubclass(list, cabc.Sequence) is True
    assert issubclass(dict, cabc.Sequence) is False
    assert cabc.Sequence.index([1, 2, 3], 3) == 2
    assert cabc.Sequence.count([1, 1, 2], 1) == 2


def test_mapping_isinstance_accepts_mappings_only() -> None:
    """`Mapping` 真只认映射类型,键值对列表与字符串都不是映射。"""
    assert isinstance({}, cabc.Mapping) is True
    assert isinstance(collections.OrderedDict(), cabc.Mapping) is True
    assert isinstance(collections.defaultdict(int), cabc.Mapping) is True
    assert isinstance(collections.Counter(), cabc.Mapping) is True
    assert isinstance([], cabc.Mapping) is False
    assert isinstance([("a", 1)], cabc.Mapping) is False
    assert isinstance("ab", cabc.Mapping) is False
    assert issubclass(dict, cabc.Mapping) is True
    assert issubclass(list, cabc.Mapping) is False
    assert cabc.Mapping.get({"a": 1}, "a") == 1
    assert cabc.Mapping.get({"a": 1}, "z", 0) == 0


def test_set_isinstance_accepts_sets_only() -> None:
    """`Set` 真只认集合类型,且可变集合与不可变集合分开归属。"""
    assert isinstance(set(), cabc.Set) is True
    assert isinstance(frozenset(), cabc.Set) is True
    assert isinstance({1, 2}, cabc.MutableSet) is True
    assert isinstance(frozenset(), cabc.MutableSet) is False
    assert isinstance([], cabc.Set) is False
    assert isinstance({}, cabc.Set) is False
    assert issubclass(set, cabc.Set) is True
    assert issubclass(frozenset, cabc.Set) is True
    assert cabc.Set.isdisjoint({1, 2}, {3, 4}) is True
    assert cabc.Set.__le__(frozenset({1}), frozenset({1, 2})) is True


def test_callable_isinstance_accepts_callables_only() -> None:
    """`Callable` 真只认可调用对象,字符串与整数都不可调用。"""
    assert isinstance(_OnlyCall(), cabc.Callable) is True
    assert isinstance(lambda: None, cabc.Callable) is True
    assert isinstance(_OnlyCall, cabc.Callable) is True
    assert isinstance(int, cabc.Callable) is True
    assert isinstance("ab", cabc.Callable) is False
    assert isinstance(5, cabc.Callable) is False
    assert isinstance([], cabc.Callable) is False
    assert issubclass(_OnlyCall, cabc.Callable) is True
    assert issubclass(int, cabc.Callable) is False
    assert _OnlyCall()() == "called"
    with pytest.raises(TypeError, match="Can't instantiate abstract class Callable"):
        cabc.Callable()


def test_sequence_subclasshook_returns_not_implemented_for_structural_class() -> None:
    """`Sequence` 在 3.11 不做结构化判定,`__subclasshook__` 真返回 NotImplemented。"""
    assert cabc.Sequence.__subclasshook__(_StructuralSequence) is NotImplemented
    assert issubclass(_StructuralSequence, cabc.Sequence) is False
    assert isinstance(_StructuralSequence(), cabc.Sequence) is False


def test_iterable_subclasshook_accepts_class_defining_dunder_iter() -> None:
    """`Iterable.__subclasshook__` 真按 `__iter__` 判定,缺方法的类被拒绝。"""
    assert cabc.Iterable.__subclasshook__(_OnlyIter) is True
    assert cabc.Iterable.__subclasshook__(_OnlyLen) is NotImplemented
    assert isinstance(_OnlyIter(), cabc.Iterable) is True
    assert isinstance(_OnlyLen(), cabc.Iterable) is False


def test_iterator_subclasshook_requires_dunder_iter_and_dunder_next() -> None:
    """`Iterator.__subclasshook__` 真要求 `__iter__` 与 `__next__` 同时存在。"""
    assert cabc.Iterator.__subclasshook__(_IterAndNext) is True
    assert cabc.Iterator.__subclasshook__(_OnlyIter) is NotImplemented
    assert isinstance(_IterAndNext(), cabc.Iterator) is True
    assert isinstance(_OnlyIter(), cabc.Iterator) is False


def test_sized_and_container_subclasshook_check_their_own_dunders() -> None:
    """`Sized` 真查 `__len__`,`Container` 真查 `__contains__`,互不顶替。"""
    assert cabc.Sized.__subclasshook__(_OnlyLen) is True
    assert cabc.Sized.__subclasshook__(_OnlyIter) is NotImplemented
    assert cabc.Container.__subclasshook__(_OnlyContains) is True
    assert cabc.Container.__subclasshook__(_OnlyLen) is NotImplemented
    assert isinstance(_OnlyLen(), cabc.Sized) is True
    assert isinstance(_OnlyContains(), cabc.Container) is True


def test_collection_subclasshook_requires_len_iter_and_contains() -> None:
    """`Collection.__subclasshook__` 真要求三个方法同时具备,少一个就拒绝。"""
    assert cabc.Collection.__subclasshook__(_FullCollection) is True
    assert cabc.Collection.__subclasshook__(_OnlyLen) is NotImplemented
    assert cabc.Collection.__subclasshook__(_OnlyIter) is NotImplemented
    assert isinstance(_FullCollection(), cabc.Collection) is True


def test_callable_subclasshook_accepts_class_defining_dunder_call() -> None:
    """`Callable.__subclasshook__` 真按 `__call__` 判定,int 没有该方法。"""
    assert cabc.Callable.__subclasshook__(_OnlyCall) is True
    assert cabc.Callable.__subclasshook__(int) is NotImplemented
    assert cabc.Callable.__subclasshook__(_OnlyIter) is NotImplemented
    assert isinstance(_OnlyCall(), cabc.Callable) is True


def test_hashable_subclasshook_accepts_class_defining_dunder_hash() -> None:
    """`Hashable.__subclasshook__` 真按 `__hash__` 判定,置 None 的类不可哈希。"""
    assert cabc.Hashable.__subclasshook__(_OnlyHash) is True
    assert cabc.Hashable.__subclasshook__(_Unhashable) is NotImplemented
    assert isinstance(_OnlyHash(), cabc.Hashable) is True
    assert isinstance(_Unhashable(), cabc.Hashable) is False


def test_reversible_subclasshook_requires_reversed_and_iter() -> None:
    """`Reversible.__subclasshook__` 真要求 `__reversed__` 与 `__iter__` 同时存在。"""
    assert cabc.Reversible.__subclasshook__(_ReversedAndIter) is True
    assert cabc.Reversible.__subclasshook__(_OnlyReversed) is NotImplemented
    assert isinstance(_ReversedAndIter(), cabc.Reversible) is True
    assert isinstance(_OnlyReversed(), cabc.Reversible) is False


def test_register_creates_virtual_subclass() -> None:
    """`register` 真把普通类登记成虚拟子类,登记类不进 `__subclasses__`。"""

    class Virtual:
        pass

    assert cabc.Sequence.register(Virtual) is Virtual
    assert issubclass(Virtual, cabc.Sequence) is True
    assert isinstance(Virtual(), cabc.Sequence) is True
    assert Virtual not in cabc.Sequence.__subclasses__()


def test_abstractmethod_blocks_instantiation_with_type_error() -> None:
    """`abstractmethod` 装饰的方法没实现时,实例化真抛 TypeError。"""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        _PartialSequence()


def test_abstractmethods_frozenset_lists_pending_abstract_methods() -> None:
    """`__abstractmethods__` 真是 frozenset,列出未实现的 `__getitem__` 与 `__len__`。"""
    assert isinstance(_PartialSequence.__abstractmethods__, frozenset)
    assert _PartialSequence.__abstractmethods__ == frozenset({"__getitem__", "__len__"})


def test_implementing_abstract_method_clears_abstractmethods() -> None:
    """补齐抽象方法后 `__abstractmethods__` 真被清空,类可正常实例化。"""

    class WithLenOnly(_PartialSequence):
        def __len__(self):
            return 0

    class Complete(_PartialSequence):
        def __len__(self):
            return 0

        def __getitem__(self, index):
            raise IndexError

    assert WithLenOnly.__abstractmethods__ == frozenset({"__getitem__"})
    assert Complete.__abstractmethods__ == frozenset()
    assert isinstance(Complete(), cabc.Sequence) is True


def test_abstract_classmethod_and_property_are_tracked() -> None:
    """抽象 classmethod 与抽象 property 真被记进 `__abstractmethods__` 并阻止实例化。"""

    class WithAbstracts(abc.ABC):
        @classmethod
        @abc.abstractmethod
        def build(cls):
            raise NotImplementedError

        @property
        @abc.abstractmethod
        def value(self):
            raise NotImplementedError

    assert WithAbstracts.__abstractmethods__ == frozenset({"build", "value"})
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        WithAbstracts()
