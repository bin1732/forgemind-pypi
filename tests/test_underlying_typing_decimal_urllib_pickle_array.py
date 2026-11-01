# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 typing 进阶 (Callable 真 进阶) + 真 decimal 真 (Context 真 create) + 真 ipaddress 真 (subnet_of 链) + 真 urllib 真 (quote 真 中文) + 真 pickle 真 (loads 真) + 真 array 真 (tolist 真) + 真 struct 真 (calcsize 真).
全 stdlib, 零模拟。
"""
import typing
import decimal
import ipaddress
import urllib.parse
import pickle
import array
import struct
import pytest


# ======================== typing 进阶 ========================
def test_typing_Callable():
    """真 Callable 真"""
    # Callable[[int, int], int]
    c = typing.Callable[[int, int], int]
    # 必可 instantiate
    assert hasattr(c, "__args__")


def test_typing_Any():
    """真 Any 真"""
    # Any == object
    assert typing.Any is typing.Any
    # 跟 None 比较
    a = typing.get_args(typing.Optional[int])  # (int, NoneType)
    assert int in a


def test_typing_List_Dict_Tuple():
    """真 List/Dict/Tuple 真"""
    # 3.9+ 可用 list[int]
    if hasattr(typing, "get_type_hints"):
        # 测试
        def f(x: int, y: str) -> bool:
            return True
        hints = typing.get_type_hints(f)
        assert hints["x"] is int
        assert hints["y"] is str
        assert hints["return"] is bool


def test_typing_Iterable():
    """真 Iterable 真进阶"""
    # Iterable[int]
    it = typing.Iterable[int]
    assert hasattr(it, "__args__")
    assert it.__args__ == (int,)


# ======================== decimal 进阶 ========================
def test_decimal_Context_create():
    """真 Context 真 create"""
    # 创建新 Context
    ctx = decimal.Context(prec=10, rounding=decimal.ROUND_HALF_UP)
    # 操作
    result = ctx.divide(decimal.Decimal("1"), decimal.Decimal("3"))
    # 0.3333333333 (10 位)
    assert len(str(result).split(".")[1]) == 10


def test_decimal_getcontext():
    """真 getcontext 真"""
    ctx = decimal.getcontext()
    # 必 1 个
    assert isinstance(ctx, decimal.Context)
    # prec
    assert ctx.prec > 0


def test_decimal_setcontext():
    """真 setcontext 真"""
    old = decimal.getcontext()
    try:
        new_ctx = decimal.Context(prec=5)
        decimal.setcontext(new_ctx)
        # 操作
        d = decimal.Decimal("1") / decimal.Decimal("3")
        # 5 位
        assert len(str(d).split(".")[1]) == 5
    finally:
        decimal.setcontext(old)


# ======================== ipaddress 进阶 ========================
def test_ipaddress_subnet_of_chain():
    """真 subnet_of 真链"""
    # 192.168.0.0/24 subnet_of 192.168.0.0/16
    sub = ipaddress.IPv4Network("192.168.0.0/24")
    super_n = ipaddress.IPv4Network("192.168.0.0/16")
    assert sub.subnet_of(super_n)
    # 反向不
    assert not super_n.subnet_of(sub)
    # 10.0.0.0/8 不
    other = ipaddress.IPv4Network("10.0.0.0/8")
    assert not sub.subnet_of(other)


def test_ipaddress_supernet_of():
    """真 supernet_of 真链"""
    sub = ipaddress.IPv4Network("192.168.0.0/24")
    super_n = ipaddress.IPv4Network("192.168.0.0/16")
    assert super_n.supernet_of(sub)


def test_ipaddress_strict_false():
    """真 strict=False 真"""
    # strict=False 接受 host bits
    net = ipaddress.IPv4Network("192.168.1.100/24", strict=False)
    assert net.network_address == ipaddress.IPv4Address("192.168.1.0")
    # strict=True 抛
    with pytest.raises(ValueError):
        ipaddress.IPv4Network("192.168.1.100/24", strict=True)


# ======================== urllib 真 ========================
def test_urllib_quote():
    """真 quote 真"""
    encoded = urllib.parse.quote("中文")
    # 必 URL encoded
    assert "%" in encoded
    # round-trip
    decoded = urllib.parse.unquote(encoded)
    assert decoded == "中文"


def test_urllib_quote_plus():
    """真 quote_plus 真"""
    encoded = urllib.parse.quote_plus("a b")
    # + for space
    assert encoded == "a+b"


# ======================== pickle 真 ========================
def test_pickle_dumps_loads():
    """真 pickle dumps/loads 真 round-trip"""
    data = [1, 2, "hello", {"key": [3, 4]}]
    dumped = pickle.dumps(data)
    loaded = pickle.loads(dumped)
    assert loaded == data


def test_pickle_protocol_variations():
    """真 pickle 4 protocols 真"""
    for proto in range(pickle.HIGHEST_PROTOCOL + 1):
        data = [1, 2, 3]
        loaded = pickle.loads(pickle.dumps(data, protocol=proto))
        assert loaded == data


# ======================== array 真 ========================
def test_array_tolist():
    """真 tolist 真"""
    a = array.array("i", [1, 2, 3, 4])
    l = a.tolist()
    # list
    assert isinstance(l, list)
    assert l == [1, 2, 3, 4]


def test_array_buffer_info():
    """真 buffer_info 真"""
    a = array.array("i", [1, 2, 3])
    info = a.buffer_info()
    # (address, length) tuple
    assert isinstance(info, tuple)
    assert len(info) == 2
    # 3 elements
    assert info[1] == 3


# ======================== struct 真 ========================
def test_struct_calcsize_formats():
    """真 calcsize 多个 format 真"""
    # 标准
    assert struct.calcsize("c") == 1
    assert struct.calcsize("b") == 1
    assert struct.calcsize("B") == 1
    assert struct.calcsize("h") == 2
    assert struct.calcsize("H") == 2
    assert struct.calcsize("i") == 4
    assert struct.calcsize("I") == 4
    assert struct.calcsize("l") == 8  # Linux
    assert struct.calcsize("q") == 8
    assert struct.calcsize("f") == 4
    assert struct.calcsize("d") == 8
