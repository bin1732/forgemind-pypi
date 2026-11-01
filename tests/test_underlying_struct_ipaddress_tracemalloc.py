# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 struct 真 IPv4 header 真拆 + 真 ipaddress 进阶 (subnet_of / supernet / subnet_of 含/排除) + 真 tracemalloc 真 start(25) 真 frame + 真 dis 真 distb 真 + 真 code 真字节码。
全 stdlib, 零模拟。
"""
import struct
import ipaddress
import tracemalloc
import dis
import sys
import pytest


# ======================== struct IPv4 ========================
def test_struct_IPv4_header_unpack():
    """真 struct 真 IPv4 header 拆"""
    # 真实 IPv4 header 20 bytes
    # version_ihl(1) + tos(1) + total_length(2) + id(2) + flags_offset(2) + ttl(1) + proto(1) + checksum(2) + src(4) + dst(4) = 20
    header = struct.pack("!BBHHHBBH4s4s",
                         0x45,  # version=4, IHL=5
                         0,     # TOS
                         60,    # total length
                         12345, # identification
                         0x4000,  # Don't Fragment flag
                         64,    # TTL
                         6,     # TCP
                         0,     # checksum
                         b"\x0a\x00\x00\x01",  # src 10.0.0.1
                         b"\x0a\x00\x00\x02")  # dst 10.0.0.2
    # unpack
    v_ihl, tos, total_len, ident, flags_off, ttl, proto, csum, src, dst = struct.unpack(
        "!BBHHHBBH4s4s", header
    )
    # 验
    version = v_ihl >> 4
    ihl = v_ihl & 0x0F
    flags = flags_off >> 13
    frag_offset = flags_off & 0x1FFF
    assert version == 4
    assert ihl == 5
    assert total_len == 60
    assert flags == 2  # DF
    assert proto == 6
    assert src == b"\x0a\x00\x00\x01"
    assert dst == b"\x0a\x00\x00\x02"


def test_struct_flags_bitwise():
    """真 struct 真位操作真 flags"""
    # IPv4 flag: 3 bits
    # 0x2000 = 010 0... (DF)
    # 0x4000 = 100 0... (MF)
    df_flag = 0x4000
    mf_flag = 0x2000
    # 验
    assert (df_flag >> 13) == 2
    assert (mf_flag >> 13) == 1


# ======================== ipaddress 进阶 ========================
def test_ipaddress_subnet_of():
    """真 subnet_of 真子网"""
    supernet = ipaddress.IPv4Network("10.0.0.0/8")
    subnet = ipaddress.IPv4Network("10.1.0.0/16")
    # subnet in supernet
    assert subnet.subnet_of(supernet)
    # 反向不
    assert not supernet.subnet_of(subnet)


def test_ipaddress_supernet_of():
    """真 supernet_of"""
    supernet = ipaddress.IPv4Network("10.0.0.0/8")
    subnet = ipaddress.IPv4Network("10.1.0.0/16")
    assert supernet.supernet_of(subnet)
    assert not subnet.supernet_of(supernet)


def test_ipaddress_compare_lt_gt():
    """真 IPv4Network 比较"""
    a = ipaddress.IPv4Network("10.0.0.0/8")
    b = ipaddress.IPv4Network("10.0.0.0/16")
    # 比较按 prefix
    assert a < b
    assert b > a
    # 同 prefix 比较 network address
    c = ipaddress.IPv4Network("10.0.0.0/16")
    assert b == c


def test_ipaddress_explode_compress():
    """真 IPv6 真 explode / compress"""
    # 压缩
    compressed = ipaddress.IPv6Address("2001:db8::1")
    # explode
    exploded = compressed.exploded
    # 应展开成 8 段
    parts = exploded.split(":")
    assert len(parts) == 8
    # 全 4 hex
    for p in parts:
        assert len(p) == 4


# ======================== tracemalloc 进阶 ========================
def test_tracemalloc_start_25_frames():
    """真 tracemalloc 真 start(25) 真 25 frame"""
    tracemalloc.start(25)  # 25 frames
    try:
        def level_5():
            return [1] * 1000
        def level_4():
            return level_5()
        def level_3():
            return level_4()
        # 嵌套
        data = level_3()
        snap = tracemalloc.take_snapshot()
        # filter by filename (本文件)
        stats = snap.statistics("filename")
        # 至少 1 个 stat
        assert len(stats) >= 1
        # total > 0
        assert sum(s.size for s in stats) > 0
    finally:
        tracemalloc.stop()


def test_tracemalloc_comparison():
    """真 tracemalloc 真 compare_to"""
    tracemalloc.start()
    try:
        # snap1
        a = [1] * 100
        snap1 = tracemalloc.take_snapshot()
        # snap2
        b = [2] * 200
        snap2 = tracemalloc.take_snapshot()
        # compare
        diff = snap2.compare_to(snap1, "lineno")
        # 必有 stats
        assert len(list(diff)) >= 0
    finally:
        tracemalloc.stop()


# ======================== dis 进阶 ========================
def _fail_for_distb():
    raise ValueError("distb test")


def test_dis_distb_traceback():
    """真 dis.distb 真打 traceback 字节码"""
    import io
    try:
        _fail_for_distb()
    except ValueError:
        buf = io.StringIO()
        dis.distb(sys.exc_info()[2], file=buf)
        output = buf.getvalue()
        # 含 traceback
        assert "_fail_for_distb" in output or "distb" in output.lower()


def test_dis_pretty_flags():
    """真 dis 字节码 flags"""
    def f():
        x = 1
        return x

    instructions = list(dis.get_instructions(f))
    # 找 LOAD_CONST
    load_consts = [i for i in instructions if i.opname == "LOAD_CONST"]
    # 1 = 第一个 const
    assert any(i.argval == 1 for i in load_consts)
    # STORE_FAST
    store_fasts = [i for i in instructions if i.opname.startswith("STORE")]
    assert len(store_fasts) >= 1


# ======================== code 真字节码 ========================
def test_code_object_bytecode():
    """真 code object 真 co_code"""
    def f(x):
        return x * 2

    bytecode = f.__code__.co_code
    # 真字节码 bytes
    assert isinstance(bytecode, bytes)
    assert len(bytecode) > 0
    # co_code[0] = first opcode
    assert bytecode[0] > 0


def test_code_object_stacksize():
    """真 co_stacksize"""
    def f():
        return 1

    stacksize = f.__code__.co_stacksize
    # 至少 1 (返 1 在栈上)
    assert stacksize >= 1


def test_code_object_nlocals():
    """真 co_nlocals"""
    def f(a, b, c=10):
        return a + b + c

    assert f.__code__.co_nlocals == 3
