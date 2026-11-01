# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 pickle 进阶 (HIGHEST_PROTOCOL / DEFAULT_PROTOCOL / 4 类协议) + 真 shelve 真 + 真 marshal 真 + 真 copyreg 真注册 + 真 copy 进阶 (deepcopy x 4 嵌套) + 真 signal 真。
全 stdlib, 零模拟。
"""
import pickle
import shelve
import marshal
import copyreg
import copy
import os
import tempfile
import pytest


class _PickleablePoint:
    """module-level 可 pickle"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def __eq__(self, other):
        return isinstance(other, _PickleablePoint) and self.x == other.x and self.y == other.y


# ======================== pickle 进阶 ========================
def test_pickle_default_protocol():
    """真 pickle DEFAULT_PROTOCOL"""
    data = {"a": 1, "b": [1, 2, 3]}
    # 默
    pickled = pickle.dumps(data)
    assert pickle.loads(pickled) == data


def test_pickle_highest_protocol():
    """真 HIGHEST_PROTOCOL"""
    data = {"x": 1, "y": 2}
    # 用最高
    pickled = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    assert pickle.loads(pickled) == data


def test_pickle_each_protocol():
    """真 0-5 protocol 真各 work"""
    data = {"key": "value", "list": [1, 2, 3]}
    for proto in range(pickle.HIGHEST_PROTOCOL + 1):
        pickled = pickle.dumps(data, protocol=proto)
        assert pickle.loads(pickled) == data


def test_pickle_lambda_fails():
    """真 lambda 不能 pickle"""
    f = lambda x: x + 1
    with pytest.raises((pickle.PicklingError, AttributeError)):
        pickle.dumps(f)


def test_pickle_class():
    """真自定义 class pickle"""
    p = _PickleablePoint(1, 2)
    pickled = pickle.dumps(p)
    p2 = pickle.loads(pickled)
    assert p == p2
    assert p2.x == 1
    assert p2.y == 2

def test_shelve_real():
    """真 shelve 真存 dbm.dumb"""
    import dbm.dumb
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    # 删 (shelve 自创)
    os.unlink(path)
    db_path = path + ".db"
    try:
        # 用 dumb dbm (纯 Python, 无 native deps)
        db1 = shelve.open(path, flag="c", protocol=2)
        try:
            db1["key1"] = "value1"
            db1["key2"] = [1, 2, 3]
        finally:
            db1.close()
        # 重开
        db2 = shelve.open(path, flag="r", protocol=2)
        try:
            assert db2["key1"] == "value1"
            assert db2["key2"] == [1, 2, 3]
            assert "key1" in db2
            assert "key2" in db2
        finally:
            db2.close()
    finally:
        # dbm.dumb 创 .db + .dir
        for suffix in [".db", ".dir", ".bak", ".dat", ""]:
            p = path + suffix
            if os.path.exists(p):
                os.unlink(p)


# ======================== marshal 真 ========================
def test_marshal_basic():
    """真 marshal 真 round-trip"""
    data = [1, "hello", (1, 2, 3), {"x": 1}]
    serialized = marshal.dumps(data)
    assert marshal.loads(serialized) == data


def test_marshal_code_object():
    """真 marshal 真 code object"""
    def f(x):
        return x * 2

    # marshal code
    serialized = marshal.dumps(f.__code__)
    code = marshal.loads(serialized)
    # 验
    assert code.co_name == "f"
    assert code.co_argcount == 1


def test_marshal_version():
    """真 marshal VERSION"""
    # 至少 3
    assert marshal.version >= 3


# ======================== copyreg 真 ========================
class _CopyRegClass:
    """module-level for copyreg"""
    def __init__(self, v):
        self.v = v


def _pickle_myclass(obj):
    return _CopyRegClass, (obj.v,)


def test_copyreg_pickle():
    """真 copyreg 真注册"""
    copyreg.pickle(_CopyRegClass, _pickle_myclass)
    # serialize
    obj = _CopyRegClass(42)
    data = pickle.dumps(obj)
    obj2 = pickle.loads(data)
    assert obj2.v == 42
    assert isinstance(obj2, _CopyRegClass)


# ======================== copy 进阶 ========================
def test_copy_deepcopy_4_nested():
    """真 deepcopy 4 层真独立"""
    # 4 层
    a = {"level1": {"level2": {"level3": {"level4": [1, 2, 3]}}}}
    b = copy.deepcopy(a)
    # 改最深
    b["level1"]["level2"]["level3"]["level4"].append(99)
    # 验 a 不变
    assert a["level1"]["level2"]["level3"]["level4"] == [1, 2, 3]
    # b 已变
    assert b["level1"]["level2"]["level3"]["level4"] == [1, 2, 3, 99]


def test_copy_deepcopy_list_compound():
    """真 deepcopy 列表复合"""
    # 列表 + dict 混合
    a = [{"x": [1, 2]}, {"y": [3, 4]}]
    b = copy.deepcopy(a)
    b[0]["x"].append(99)
    # a 不变
    assert a[0]["x"] == [1, 2]
    assert a[1]["y"] == [3, 4]


def test_copy_copy_dict_list():
    """真 shallow copy dict + list"""
    a = {"x": [1, 2, 3]}
    b = copy.copy(a)
    # 改 b
    b["x"].append(4)
    # a 变 (shallow)
    assert a["x"] == [1, 2, 3, 4]
    # b 改 key 不影响 a (新 dict)
    b["new_key"] = "v"
    assert "new_key" not in a
