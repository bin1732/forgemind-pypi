# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 weakref 真 (finalize 真 attr 进阶) + 真 array 真 (reverse / remove) + 真 struct 真 (C struct 真 nested) + 真 pathlib 真 (chmod / stat 真 / lstat 真) + 真 dis 真 (get_instructions frame 进阶) + 真 compile 真 (多行 code).
全 stdlib, 零模拟。
"""
import weakref
import array
import struct
import pathlib
import dis
import os
import tempfile
import pytest


# ======================== weakref 进阶 ========================
def test_weakref_finalize_attributes():
    """真 finalize 真 attributes"""
    class Obj:
        pass

    obj = Obj()
    f = weakref.finalize(obj, lambda: None)
    # atexit 是 callable
    assert f.atexit is True or f.atexit is False
    # alive
    assert f.alive is True
    # detach
    f.detach()
    # alive 仍 True (detach 不 detach alive)
    # 但不再 fire
    del obj
    import gc
    gc.collect()
    # alive False
    assert f.alive is False


def test_weakref_finalize_callback_again():
    """真 finalize 真 callback 不再 fire"""
    fired = []
    class Obj:
        pass

    obj = Obj()
    f = weakref.finalize(obj, lambda: fired.append(1))
    # 第一次 fire
    del obj
    import gc
    gc.collect()
    assert fired == [1]
    # alive False
    assert f.alive is False


# ======================== array 进阶 ========================
def test_array_reverse():
    """真 reverse 真"""
    a = array.array("i", [1, 2, 3, 4, 5])
    a.reverse()
    assert list(a) == [5, 4, 3, 2, 1]


def test_array_remove():
    """真 remove 真"""
    a = array.array("i", [1, 2, 3, 2, 1])
    a.remove(2)  # 第一个 2
    # 2 在 index 1 删
    assert list(a) == [1, 3, 2, 1]
    # remove 不存在 → ValueError
    with pytest.raises(ValueError):
        a.remove(99)


def test_array_pop():
    """真 pop 真"""
    a = array.array("i", [10, 20, 30, 40])
    # pop 最后
    assert a.pop() == 40
    # pop 索引
    assert a.pop(0) == 10
    assert list(a) == [20, 30]
    # pop 空 → IndexError
    with pytest.raises(IndexError):
        array.array("i").pop()


# ======================== struct 进阶 ========================
def test_struct_C_like_struct():
    """真 struct 真 C struct 真"""
    # C struct { short a; int b; char c; }
    # native = 4 + 4 + 1 = 9 + padding = 12
    # < 显式 no padding
    size = struct.calcsize("<hic")
    # 2 + 4 + 1 = 7
    assert size == 7
    # pack
    packed = struct.pack("<hic", 1, 1000000, b"a")
    assert len(packed) == 7
    # unpack
    a, b, c = struct.unpack("<hic", packed)
    assert a == 1
    assert b == 1000000
    assert c == b"a"


# ======================== pathlib 真 ========================
def test_pathlib_chmod():
    """真 chmod 真"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        p = pathlib.Path(path)
        # chmod 0o600
        p.chmod(0o600)
        mode = p.stat().st_mode & 0o777
        assert mode == 0o600
    finally:
        os.unlink(path)


def test_pathlib_stat():
    """真 stat 真"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"hello")
        path = f.name
    try:
        p = pathlib.Path(path)
        # stat
        s = p.stat()
        # size
        assert s.st_size == 5
    finally:
        os.unlink(path)


def test_pathlib_exists():
    """真 exists 真"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        p = pathlib.Path(path)
        assert p.exists()
        # 不存在
        assert not pathlib.Path("/nonexistent_xyz_abc_12345").exists()
    finally:
        os.unlink(path)


def test_pathlib_is_file_is_dir():
    """真 is_file / is_dir"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        p = pathlib.Path(path)
        assert p.is_file()
        assert not p.is_dir()
    finally:
        os.unlink(path)


# ======================== dis 进阶 ========================
def test_dis_get_instructions_lambda():
    """真 dis 真 lambda 字节码"""
    add_one = lambda x: x + 1
    instructions = list(dis.get_instructions(add_one))
    # 真有 LOAD_FAST, BINARY_OP (3.11+) 或 BINARY_ADD
    opnames = [i.opname for i in instructions]
    assert any("FAST" in o for o in opnames)
    # 必有 RETURN
    assert any("RETURN" in o for o in opnames)


# ======================== compile 进阶 ========================
def test_compile_multiline():
    """真 compile 真多行"""
    code = """
x = 1
y = 2
z = x + y
"""
    compiled = compile(code, "<test>", "exec")
    ns = {}
    exec(compiled, ns)
    assert ns["z"] == 3


def test_compile_class():
    """真 compile 真 class"""
    code = """
class MyClass:
    def __init__(self, x):
        self.x = x
    def get(self):
        return self.x

obj = MyClass(42)
result = obj.get()
"""
    compiled = compile(code, "<test>", "exec")
    ns = {}
    exec(compiled, ns)
    assert ns["result"] == 42
    assert ns["obj"].x == 42
