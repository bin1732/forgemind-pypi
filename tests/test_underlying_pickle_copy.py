# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 pickle / copy / struct / base64 / uuid — 真序列化真还原, 不走 mock。
1MB+ 数据真走 pickle 序列化, 验 100% round-trip。
"""
import base64
import copy
import os
import pickle
import struct
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pytest


@dataclass
class Point:
    x: float
    y: float
    name: str = ""


def test_pickle_int_round_trip():
    """pickle int 真序列化真还原"""
    for n in [0, 1, -1, 2**63, -2**63, 2**100]:
        data = pickle.dumps(n)
        restored = pickle.loads(data)
        assert restored == n, f"pickle({n}) 应原样, 实际 {restored}"


def test_pickle_string_round_trip():
    """pickle string 真序列化真还原"""
    s = "Hello, 世界! 🌍"
    data = pickle.dumps(s)
    restored = pickle.loads(data)
    assert restored == s, f"pickle string 应 100% 还原"


def test_pickle_bytes_round_trip():
    """pickle bytes 真序列化真还原"""
    b = os.urandom(1024 * 1024)  # 1 MiB
    data = pickle.dumps(b)
    restored = pickle.loads(data)
    assert restored == b, f"1MiB pickle 应 100% 还原, 实际 {len(restored)}/{len(b)}"


def test_pickle_dataclass_round_trip():
    """pickle dataclass 真序列化 (含 type)"""
    p = Point(x=1.5, y=2.5, name="forge")
    data = pickle.dumps(p)
    restored = pickle.loads(data)
    assert isinstance(restored, Point)
    assert restored.x == 1.5
    assert restored.y == 2.5
    assert restored.name == "forge"


def test_pickle_nested_structure():
    """pickle 真序列化嵌套 dict/list"""
    nested = {
        "a": [1, 2, [3, 4, {"b": "c"}]],
        "d": {"e": [None, True, False, 0, 1.5, "x"]},
        "f": set([1, 2, 3]),
    }
    data = pickle.dumps(nested)
    restored = pickle.loads(data)
    assert restored["a"] == [1, 2, [3, 4, {"b": "c"}]]
    assert restored["d"]["e"] == [None, True, False, 0, 1.5, "x"]
    # set 还原后 type 一致
    assert isinstance(restored["f"], set)
    assert restored["f"] == {1, 2, 3}


def test_pickle_circular_reference():
    """pickle 真能处理循环引用"""
    a = []
    a.append(a)  # a 含自己
    data = pickle.dumps(a)
    restored = pickle.loads(data)
    # restored[0] is restored
    assert restored[0] is restored, f"循环引用应还原, 实际 {restored[0] is restored}"


def test_copy_deepcopy_truly_independent():
    """copy.deepcopy 真深拷 (改 copy 不影响原)"""
    original = [[1, 2, 3], {"a": [4, 5]}]
    deep = copy.deepcopy(original)
    # 改 deep 不影响 original
    deep[0].append(99)
    deep[1]["a"].append(99)
    assert original == [[1, 2, 3], {"a": [4, 5]}], (
        f"deepcopy 应独立, 实际 original 改了: {original}"
    )


def test_copy_shallow_shares_inner_list():
    """copy.copy 真浅拷 (内层 list 共享)"""
    original = [[1, 2, 3], [4, 5]]
    shallow = copy.copy(original)
    # 改 inner
    shallow[0].append(99)
    # original 也应改 (共享)
    assert original[0] == [1, 2, 3, 99], f"shallow copy 共享内层, 实际: {original[0]}"


def test_struct_pack_unpack_int():
    """struct 真 pack/unpack int (大端/小端)"""
    # 大端 32-bit
    packed = struct.pack(">I", 0x12345678)
    assert packed == b"\x12\x34\x56\x78"
    assert struct.unpack(">I", packed)[0] == 0x12345678
    # 小端 32-bit
    packed = struct.pack("<I", 0x12345678)
    assert packed == b"\x78\x56\x34\x12"
    assert struct.unpack("<I", packed)[0] == 0x12345678


def test_struct_pack_unpack_float():
    """struct 真 pack/unpack double (IEEE 754)"""
    packed = struct.pack("<d", 3.14159)
    assert len(packed) == 8
    restored, = struct.unpack("<d", packed)
    assert abs(restored - 3.14159) < 1e-10, f"double round-trip 精度差 {abs(restored - 3.14159)}"


def test_base64_encode_decode_real():
    """base64 真编解码"""
    data = b"Hello, World! " * 100
    encoded = base64.b64encode(data)
    decoded = base64.b64decode(encoded)
    assert decoded == data


def test_base64_urlsafe_no_special_chars():
    """base64 urlsafe 不含 + / ="""
    data = b"\xff\xfe\xfd" * 100  # 含 padding
    encoded = base64.urlsafe_b64encode(data)
    # urlsafe 没用 = padding (除非 strip)
    for c in encoded.decode():
        assert c.isalnum() or c in "-_", f"urlsafe 不应有 {c!r}"


def test_uuid4_uniqueness():
    """uuid4 真产 1000 个不同 UUID"""
    uuids = {str(uuid.uuid4()) for _ in range(1000)}
    assert len(uuids) == 1000, f"1000 UUID 应唯一, 实际 {len(uuids)}"


def test_uuid4_format_real():
    """uuid4 真匹配 8-4-4-4-12 hex 格式"""
    u = uuid.uuid4()
    s = str(u)
    parts = s.split("-")
    assert len(parts) == 5
    assert len(parts[0]) == 8
    assert len(parts[1]) == 4
    assert len(parts[2]) == 4
    assert len(parts[3]) == 4
    assert len(parts[4]) == 12


def test_uuid4_version_actually_4():
    """uuid4 真 version 4 (第 13 nibble = 4)"""
    u = uuid.uuid4()
    # version 在第 14 个 hex char (index 14, 倒数第 3 段第一个)
    assert str(u)[14] == "4", f"uuid4 第 14 字符应 '4', 实际: {str(u)}"


def test_uuid1_includes_mac_address():
    """uuid1 真含 MAC 地址 (或随机 fallback)"""
    u = uuid.uuid1()
    # uuid1.node 字段含 MAC
    node = u.node
    # MAC 6 字节
    assert isinstance(node, int)
    assert 0 <= node < 2**48


def test_uuid5_deterministic():
    """uuid5 真 deterministic (同样 namespace+name → 同 UUID)"""
    u1 = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")
    u2 = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")
    assert u1 == u2
    u3 = uuid.uuid5(uuid.NAMESPACE_DNS, "different.com")
    assert u1 != u3


def test_struct_calcsize_accurate():
    """struct.calcsize 真算实际字节数"""
    assert struct.calcsize("i") == 4
    assert struct.calcsize("q") == 8
    assert struct.calcsize("d") == 8
    assert struct.calcsize("ii") == 8
    assert struct.calcsize("iid") == 16
    assert struct.calcsize("10s") == 10
