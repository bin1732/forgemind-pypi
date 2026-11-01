# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 collections 进阶: namedtuple 进阶 (rename/asdict/_replace) + OrderedDict (move_to_end/popitem) + Counter 进阶 (most_common/subtract) + ChainMap 真 + UserDict/UserList/UserString + defaultdict。
全 stdlib, 零模拟。
"""
import collections
import collections.abc
import pytest


# ======================== namedtuple 进阶 ========================
def test_namedtuple_basic():
    """真 namedtuple"""
    Point = collections.namedtuple("Point", ["x", "y"])
    p = Point(1, 2)
    assert p.x == 1
    assert p.y == 2
    # 解包
    x, y = p
    assert (x, y) == (1, 2)


def test_namedtuple_asdict():
    """真 _asdict"""
    Point = collections.namedtuple("Point", ["x", "y"])
    p = Point(1, 2)
    d = p._asdict()
    assert d == {"x": 1, "y": 2}


def test_namedtuple_replace():
    """真 _replace 真返回新"""
    Point = collections.namedtuple("Point", ["x", "y"])
    p = Point(1, 2)
    p2 = p._replace(x=99)
    assert p.x == 1  # 原不变
    assert p2.x == 99
    assert p2.y == 2


def test_namedtuple_rename():
    """真 rename=True 自动冲突"""
    # 关键字冲突
    Point = collections.namedtuple("Point", ["x", "class", "y"], rename=True)
    # 'class' → '_1'
    p = Point(1, 2, 3)
    assert p._1 == 2  # 'class' 重命名


# ======================== OrderedDict 进阶 ========================
def test_ordereddict_move_to_end():
    """真 move_to_end"""
    d = collections.OrderedDict([("a", 1), ("b", 2), ("c", 3)])
    d.move_to_end("a")
    # 顺序 a, c, b? 实际: b, c, a (a 移到末尾)
    assert list(d.keys()) == ["b", "c", "a"]


def test_ordereddict_popitem():
    """真 popitem 真取 LIFO/FIFO"""
    d = collections.OrderedDict([("a", 1), ("b", 2), ("c", 3)])
    # 默认 LIFO (last=True)
    key, val = d.popitem()
    assert (key, val) == ("c", 3)
    # FIFO (last=False)
    key2, val2 = d.popitem(last=False)
    assert (key2, val2) == ("a", 1)


def test_ordereddict_equality():
    """真 OrderedDict == 比较值 + 顺序"""
    d1 = collections.OrderedDict([("a", 1), ("b", 2)])
    d2 = collections.OrderedDict([("b", 2), ("a", 1)])
    # 同 key value 不同序 → 不等
    assert d1 != d2
    # 同 key value 同序 → 等
    d3 = collections.OrderedDict([("a", 1), ("b", 2)])
    assert d1 == d3


# ======================== Counter 进阶 ========================
def test_counter_most_common():
    """真 most_common"""
    c = collections.Counter("abracadabra")
    # a:5, b:2, r:2, c:1, d:1
    assert c.most_common(3) == [("a", 5), ("b", 2), ("r", 2)]


def test_counter_subtract():
    """真 subtract 真减"""
    c1 = collections.Counter(a=4, b=2)
    c2 = collections.Counter(a=1, b=3)
    c1.subtract(c2)
    # a: 4-1=3, b: 2-3=-1
    assert c1["a"] == 3
    assert c1["b"] == -1


def test_counter_total():
    """真 total 真总"""
    c = collections.Counter(a=3, b=2, c=1)
    assert c.total() == 6


def test_counter_arithmetic():
    """真 Counter 算术"""
    c1 = collections.Counter(a=3, b=1)
    c2 = collections.Counter(a=1, b=2)
    # 加 (per-key max)
    c_add = c1 + c2
    assert c_add["a"] == 4
    assert c_add["b"] == 3
    # 减 (per-key min(0))
    c_sub = c1 - c2
    assert c_sub["a"] == 2
    assert c_sub["b"] == 0  # 1-2 负数舍去
    # 交 (per-key min)
    c_inter = c1 & c2
    assert c_inter["a"] == 1
    assert c_inter["b"] == 1
    # 并 (per-key max)
    c_union = c1 | c2
    assert c_union["a"] == 3
    assert c_union["b"] == 2


# ======================== ChainMap ========================
def test_chainmap_lookup():
    """真 ChainMap 真查"""
    d1 = {"a": 1, "b": 2}
    d2 = {"b": 3, "c": 4}
    cm = collections.ChainMap(d1, d2)
    # 查 d1 优先
    assert cm["a"] == 1
    assert cm["b"] == 2  # d1
    assert cm["c"] == 4  # d2


def test_chainmap_new_child():
    """真 new_child 真加新 scope"""
    d1 = {"a": 1}
    d2 = {"a": 2}
    cm = collections.ChainMap(d1)
    cm2 = cm.new_child(d2)
    # 新 scope 优先
    assert cm2["a"] == 2
    # 旧 cm 仍 d1
    assert cm["a"] == 1


# ======================== defaultdict ========================
def test_defaultdict_list():
    """真 defaultdict list"""
    d = collections.defaultdict(list)
    d["a"].append(1)
    d["a"].append(2)
    d["b"].append(3)
    assert d["a"] == [1, 2]
    assert d["b"] == [3]
    # 访问不存在 key 不创建 (只 get)
    # 但 __getitem__ 会创建
    assert "c" not in d


def test_defaultdict_int():
    """真 defaultdict int"""
    d = collections.defaultdict(int)
    d["a"] += 1
    d["a"] += 1
    d["b"] += 10
    assert d["a"] == 2
    assert d["b"] == 10


# ======================== UserDict / UserList / UserString ========================
def test_userdict_subclass():
    """真 UserDict 真子类化"""
    class MyDict(collections.UserDict):
        def __setitem__(self, key, value):
            super().__setitem__(key.upper(), value)

    d = MyDict()
    d["a"] = 1
    # key 已转大写
    assert d["A"] == 1


def test_userstring_subclass():
    """真 UserString 真子类化"""
    class MyStr(collections.UserString):
        def upper(self):
            return MyStr(self.data.upper() + "!")

    s = MyStr("hello")
    uppered = s.upper()
    assert "!" in uppered.data


def test_userlist_subclass():
    """真 UserList 真子类化"""
    class MyList(collections.UserList):
        def append(self, item):
            if item > 0:
                super().append(item)

    lst = MyList([1, 2, 3])
    lst.append(-1)  # 不加
    lst.append(4)   # 加
    assert 4 in lst.data
    assert -1 not in lst.data
