# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 ipaddress 进阶 (IPv4 拆分 / hosts() / num_addresses) + 真 struct 进阶 (UUID 真 16 bytes) + 真 uuid 进阶 (uuid3 / namespace 真 dict) + 真 copy 真注册 __deepcopy__ + 真 contextvars 真 vars.
全 stdlib, 零模拟。
"""
import ipaddress
import struct
import uuid
import copy
import contextvars
import pytest


# ======================== ipaddress 进阶 ========================
def test_ipaddress_hosts():
    """真 hosts() 真取可用 IPs (排除 network/broadcast)"""
    net = ipaddress.IPv4Network("10.0.0.0/29")
    # /29 = 8 IPs, hosts = 6 (排除 .0 和 .7)
    hosts = list(net.hosts())
    assert len(hosts) == 6
    assert hosts[0] == ipaddress.IPv4Address("10.0.0.1")
    assert hosts[-1] == ipaddress.IPv4Address("10.0.0.6")


def test_ipaddress_num_addresses():
    """真 num_addresses 真"""
    # /24 = 256
    n24 = ipaddress.IPv4Network("10.0.0.0/24")
    assert n24.num_addresses == 256
    # /16 = 65536
    n16 = ipaddress.IPv4Network("10.0.0.0/16")
    assert n16.num_addresses == 65536
    # /0 = 2^32
    n0 = ipaddress.IPv4Network("0.0.0.0/0")
    assert n0.num_addresses == 2**32


def test_ipaddress_broadcast_network():
    """真 broadcast / network 真"""
    net = ipaddress.IPv4Network("10.0.0.0/24")
    assert str(net.network_address) == "10.0.0.0"
    assert str(net.broadcast_address) == "10.0.0.255"
    # /31 没 broadcast
    net_31 = ipaddress.IPv4Network("10.0.0.0/31")
    # 0 = 10.0.0.0, 1 = 10.0.0.1 (无 broadcast)
    assert str(net_31.broadcast_address) == "10.0.0.1"


def test_ipaddress_is_private():
    """真 is_private 真"""
    # 10.0.0.0/8 是 private
    assert ipaddress.IPv4Address("10.0.0.1").is_private
    # 192.168.0.0/16 是
    assert ipaddress.IPv4Address("192.168.1.1").is_private
    # 8.8.8.8 不是
    assert not ipaddress.IPv4Address("8.8.8.8").is_private


def test_ipaddress_is_loopback():
    """真 is_loopback 真"""
    assert ipaddress.IPv4Address("127.0.0.1").is_loopback
    assert ipaddress.IPv4Address("127.0.0.99").is_loopback
    assert not ipaddress.IPv4Address("10.0.0.1").is_loopback


def test_ipaddress_subnet_of_chain():
    """真 subnet_of 真多层"""
    a = ipaddress.IPv4Network("10.0.0.0/8")
    b = ipaddress.IPv4Network("10.1.0.0/16")
    c = ipaddress.IPv4Network("10.1.2.0/24")
    # 链
    assert c.subnet_of(b)
    assert c.subnet_of(a)
    assert b.subnet_of(a)


# ======================== struct UUID ========================
def test_struct_UUID_pack_unpack():
    """真 struct UUID 16 bytes pack/unpack"""
    # 真实 UUID
    u = uuid.uuid4()
    # pack 成 16 bytes
    # UUID: 4 bytes time_low + 2 time_mid + 2 time_hi + 2 clk_seq + 6 node
    packed = struct.pack(">IHHH6s",
                         u.time_low, u.time_mid, u.time_hi_version,
                         u.clock_seq_hi_variant, u.node.to_bytes(6, "big"))
    assert len(packed) == 16
    # unpack
    tl, tm, thv, cshv, n = struct.unpack(">IHHH6s", packed)
    assert tl == u.time_low


def test_struct_double_pack():
    """真 struct 真 double"""
    import math
    # pack 8 byte double
    packed = struct.pack(">d", math.pi)
    assert len(packed) == 8
    val, = struct.unpack(">d", packed)
    assert abs(val - math.pi) < 1e-15


# ======================== uuid 进阶 ========================
def test_uuid3_namespace():
    """真 uuid3 真 MD5 namespace"""
    # 真 deterministic
    u1 = uuid.uuid3(uuid.NAMESPACE_DNS, "python.org")
    u2 = uuid.uuid3(uuid.NAMESPACE_DNS, "python.org")
    assert u1 == u2
    assert u1.version == 3


def test_uuid_int_to_uuid():
    """真 int → UUID 真"""
    # 16 字节
    u = uuid.UUID(int=0x1234567890ABCDEF1234567890ABCDEF)
    # 32 hex
    assert len(u.hex) == 32


def test_uuid_bytes_to_uuid():
    """真 bytes → UUID 真"""
    raw = b"\x12\x34\x56\x78\x90\xab\xcd\xef\x12\x34\x56\x78\x90\xab\xcd\xef"
    u = uuid.UUID(bytes=raw)
    assert u.bytes == raw


def test_uuid_fields():
    """真 UUID 真 fields"""
    u = uuid.uuid4()
    # 5 fields
    assert isinstance(u.time_low, int)
    assert isinstance(u.time_mid, int)
    assert isinstance(u.time_hi_version, int)
    assert isinstance(u.clock_seq_hi_variant, int)
    assert isinstance(u.clock_seq_low, int)
    assert isinstance(u.node, int)


# ======================== copy 注册 __deepcopy__ ========================
def test_copy_deepcopy_with_dunder():
    """真 deepcopy 真 __deepcopy__ 真调"""
    class Custom:
        def __init__(self, data):
            self.data = data
            self.copy_count = 0
        def __deepcopy__(self, memo):
            # 自定义 deepcopy
            new = Custom(copy.deepcopy(self.data, memo))
            new.copy_count = self.copy_count + 1
            return new

    original = Custom({"key": [1, 2, 3]})
    deep = copy.deepcopy(original)
    # 真调 __deepcopy__
    assert deep.copy_count == 1
    # data 独立
    deep.data["key"].append(99)
    assert original.data["key"] == [1, 2, 3]


# ======================== contextvars 真 vars ========================
def test_contextvars_nested_run_call():
    """真 contextvars 真嵌套 copy + run"""
    var = contextvars.ContextVar("test_nested", default="init")
    # 设 父
    var.set("parent")
    # 子 ctx
    ctx = contextvars.copy_context()
    def task():
        # 子 ctx 看到 default (copy 复制)
        return var.get()
    # run 后返回值
    result = ctx.run(task)
    # 父 ctx 仍 parent
    assert var.get() == "parent"
    # 子 ctx 内 default
    # 但 copy_context 复制了父, 所以也是 parent
    # 改 — 在新 ctx set
    ctx2 = contextvars.copy_context()
    def task2():
        var.set("child")
        return var.get()
    assert ctx2.run(task2) == "child"
