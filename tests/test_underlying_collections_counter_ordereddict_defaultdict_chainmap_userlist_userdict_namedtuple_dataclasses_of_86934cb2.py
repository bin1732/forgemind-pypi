# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`collections.Counter/OrderedDict/Defaultdict/ChainMap/UserList/UserDict` + `collections.namedtuple` + `dataclasses` + `enum` 进阶 + `ipaddress` Network 真 `overlaps/subnet_of/supernet_of/compare_subnets` 真底层测试。

覆盖 collections Counter/OrderedDict/Defaultdict/ChainMap/UserList/UserDict/namedtuple / dataclasses / enum auto/Flag/IntEnum/nonmember / ipaddress overlaps/subnet_of/supernet_of/compare_subnets 模块:
  - `collections.Counter 真统计 计数`
  - `collections.OrderedDict 真保序 + move_to_end`
  - `collections.defaultdict 真创 + 缺 key 不抛`
  - `collections.ChainMap 真 chained 2 dicts`
  - `collections.UserDict 真子化 + 字典语义`
  - `collections.UserList 真子化 + list 语义`
  - `collections.namedtuple 真创 + field 访问`
  - `collections.namedtuple 真 _replace + _asdict`
  - `dataclasses 真创 + field + default_factory`
  - `dataclasses.asdict 真转 dict`
  - `dataclasses.astuple 真转 tuple`
  - `dataclasses.replace 真 replace field`
  - `dataclasses.fields 真返 Field tuple`
  - `enum.auto() 真连续`
  - `enum.Flag 真 OR + member`
  - `enum.IntEnum 真 int + Enum 双重`
  - `enum.unique 真拒绝重复 value`
  - `ipaddress.IPv4Network.overlaps 真返 True/False`
  - `ipaddress.IPv4Network.subnet_of True/False`
  - `ipaddress.IPv4Network.supernet_of True/False`
  - `ipaddress.IPv4Network.compare_networks 排序 key`
"""
import collections
import dataclasses
import enum
import ipaddress
import sys

import pytest


# -- collections ------------------------------------------------------------

class TestCollectionsAdvanced:
    def test_Counter(self):
        """`collections.Counter 真统计 计数。"""
        c = collections.Counter("forge forge hello")
        # 必计数
        assert c["f"] == 2
        # 'r' = 2 (forge forge)
        assert c["r"] == 2
        # 'h' = 1 (hello 1)
        assert c["h"] == 1
        # 'l' = 2 (hello 2 个 l)
        assert c["l"] == 2
        # 必 most_common
        most = c.most_common(2)
        # 2 most common
        assert len(most) == 2

    def test_OrderedDict(self):
        """`OrderedDict 真保序 + move_to_end。"""
        od = collections.OrderedDict()
        od["a"] = 1
        od["b"] = 2
        od["c"] = 3
        # 必保序
        assert list(od.keys()) == ["a", "b", "c"]
        # move_to_end
        od.move_to_end("a")
        assert list(od.keys()) == ["b", "c", "a"]

    def test_defaultdict(self):
        """`defaultdict 真创 + 缺 key 不抛。"""
        dd = collections.defaultdict(list)
        # 缺 key 必不抛 + 返 []
        assert dd["missing"] == []
        # 必是 list
        dd["x"].append("forge")
        assert dd["x"] == ["forge"]

    def test_ChainMap(self):
        """`ChainMap 真 chained 2 dicts。"""
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 99, "c": 3}
        cm = collections.ChainMap(d1, d2)
        # d1 优先
        assert cm["a"] == 1
        assert cm["b"] == 2  # d1 优先
        assert cm["c"] == 3

    def test_UserDict(self):
        """`UserDict 真子化 + 字典语义。"""
        class MyDict(collections.UserDict):
            pass

        d = MyDict({"a": 1, "b": 2})
        # 必 dict 语义
        assert d["a"] == 1
        assert len(d) == 2
        # 必能 iter
        keys = list(d.keys())
        assert "a" in keys

    def test_UserList(self):
        """`UserList 真子化 + list 语义。"""
        class MyList(collections.UserList):
            pass

        l = MyList([1, 2, 3])
        # 必 list 语义
        assert len(l) == 3
        assert l[0] == 1
        # 必能 append
        l.append(4)
        assert l[3] == 4


# -- collections.namedtuple -------------------------------------------------

Point = collections.namedtuple("Point", ["x", "y"])


class TestNamedTupleV2:
    def test_namedtuple_field_access(self):
        """`namedtuple 真创 + field 访问。"""
        p = Point(3, 4)
        assert p.x == 3
        assert p.y == 4
        # index
        assert p[0] == 3
        # tuple methods
        assert len(p) == 2

    def test_namedtuple_replace_asdict(self):
        """`namedtuple _replace + _asdict。"""
        p = Point(3, 4)
        p2 = p._replace(x=99)
        assert p2.x == 99
        # _asdict
        d = p._asdict()
        assert d == {"x": 3, "y": 4}


# -- dataclasses ------------------------------------------------------------

@dataclasses.dataclass
class PointDC:
    x: int
    y: int = 0


@dataclasses.dataclass
class WithFactory:
    items: list = dataclasses.field(default_factory=list)


class TestDataclassesV2:
    def test_dataclass_field(self):
        """`dataclass 真创 + field + default_factory。"""
        p = PointDC(3, 4)
        assert p.x == 3
        assert p.y == 4
        # default
        p2 = PointDC(99)
        assert p2.x == 99
        assert p2.y == 0
        # factory
        wf = WithFactory()
        wf.items.append("forge")
        assert wf.items == ["forge"]

    def test_asdict_astuple(self):
        """`asdict + astuple 真转。"""
        p = PointDC(3, 4)
        d = dataclasses.asdict(p)
        assert d == {"x": 3, "y": 4}
        t = dataclasses.astuple(p)
        assert t == (3, 4)

    def test_replace_fields(self):
        """`dataclasses.replace + fields 真返。"""
        p = PointDC(3, 4)
        p2 = dataclasses.replace(p, x=99)
        assert p2.x == 99
        # fields 真返 (Field, ...)
        fields = dataclasses.fields(PointDC)
        assert len(fields) == 2
        assert fields[0].name == "x"


# -- enum 进阶 ---------------------------------------------------------------

class TestEnumV2:
    def test_auto(self):
        """`enum.auto() 真连续。"""
        class Color(enum.Enum):
            RED = enum.auto()
            GREEN = enum.auto()
            BLUE = enum.auto()

        # 必连续
        assert Color.RED.value == 1
        assert Color.GREEN.value == 2
        assert Color.BLUE.value == 3

    def test_Flag_OR(self):
        """`Flag 真 OR 组合。"""
        class Perm(enum.Flag):
            R = 1
            W = 2
            X = 4

        rw = Perm.R | Perm.W
        # 必含 R + W
        assert Perm.R in rw
        assert Perm.W in rw
        # 必不含 X
        assert Perm.X not in rw

    def test_IntEnum(self):
        """`IntEnum 真 int + Enum 双重。"""
        class Status(enum.IntEnum):
            OK = 200
            NOT_FOUND = 404

        # 必 is int
        assert isinstance(Status.OK, int)
        # 必 is Status
        assert isinstance(Status.OK, Status)
        # ==
        assert Status.OK == 200

    def test_unique(self):
        """`enum.unique 拒绝重复 value。"""
        with pytest.raises(ValueError):
            @enum.unique
            class DupEnum(enum.Enum):
                A = 1
                B = 1  # 重复 value 必抛


# -- ipaddress 进阶 ---------------------------------------------------------

class TestIpaddressAdvancedV6:
    def test_IPv4Network_overlaps(self):
        """`IPv4Network.overlaps 真返 True/False。"""
        n1 = ipaddress.IPv4Network("192.168.0.0/24")
        n2 = ipaddress.IPv4Network("192.168.0.0/26")
        n3 = ipaddress.IPv4Network("10.0.0.0/24")
        # 必 overlap
        assert n1.overlaps(n2) is True
        # 必不 overlap
        assert n1.overlaps(n3) is False

    def test_IPv4Network_subnet_of(self):
        """`IPv4Network.subnet_of True/False。"""
        big = ipaddress.IPv4Network("10.0.0.0/8")
        small = ipaddress.IPv4Network("10.1.0.0/16")
        # small subnet_of big
        assert small.subnet_of(big) is True
        # big not subnet_of small
        assert big.subnet_of(small) is False

    def test_IPv4Network_supernet_of(self):
        """`IPv4Network.supernet_of True/False。"""
        big = ipaddress.IPv4Network("10.0.0.0/8")
        small = ipaddress.IPv4Network("10.1.0.0/16")
        # big supernet_of small
        assert big.supernet_of(small) is True
        # small not supernet_of big
        assert small.supernet_of(big) is False

    def test_IPv4Network_compare_networks(self):
        """`IPv4Network.compare_networks 真实例 method。"""
        n1 = ipaddress.IPv4Network("10.0.0.0/24")
        n2 = ipaddress.IPv4Network("10.0.0.0/8")
        # compare_networks 是 method (需 other)
        result = n1.compare_networks(n2)
        # 必是 int (-1, 0, 1)
        assert isinstance(result, int)
        # /24 > /8 (more specific) → 必返 1
        assert result == 1
        # 同样 prefixlen: 必返 0
        n3 = ipaddress.IPv4Network("10.0.0.0/24")
        assert n1.compare_networks(n3) == 0
