# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 copy 进阶 (深/浅) + 真 shutil + 真 tempfile + 真 uuid + 真 fileinput。
全 stdlib, 零模拟。
"""
import copy
import shutil
import tempfile
import uuid
import fileinput
import os
import pathlib
import pytest


# ======================== copy ========================
def test_copy_deepcopy_nested():
    """真 deepcopy 嵌套真独立"""
    original = {"a": [1, 2, {"b": 3}]}
    deep = copy.deepcopy(original)
    deep["a"][2]["b"] = 999
    # 原始不变
    assert original["a"][2]["b"] == 3
    assert deep["a"][2]["b"] == 999


def test_copy_shallowcopy_nested_shared():
    """真 shallow copy 嵌套共享"""
    original = {"a": [1, 2, 3]}
    shallow = copy.copy(original)
    shallow["a"].append(4)
    # 原始也变 (共享)
    assert original["a"] == [1, 2, 3, 4]


def test_copy_deepcopy_circular():
    """真 deepcopy 处理循环引用"""
    a = []
    a.append(a)
    b = copy.deepcopy(a)
    # 长度同
    assert len(b) == 1
    # 独立 — b 不 is a
    assert b[0] is not a
    # 但 self-referencing
    assert b[0] is b


def test_copy_with_object():
    """真 deepcopy 自定义对象"""
    class Box:
        def __init__(self, v):
            self.v = v
        def __eq__(self, other):
            return isinstance(other, Box) and self.v == other.v

    original = Box([1, 2, 3])
    deep = copy.deepcopy(original)
    deep.v.append(4)
    assert original.v == [1, 2, 3]
    assert deep.v == [1, 2, 3, 4]


# ======================== shutil ========================
def test_shutil_copy_file():
    """真 shutil.copy 真文件真复制"""
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / "src.txt"
        dst = pathlib.Path(d) / "dst.txt"
        src.write_text("hello world")
        shutil.copy(str(src), str(dst))
        assert dst.read_text() == "hello world"
        # metadata 保留
        assert src.stat().st_mode == dst.stat().st_mode


def test_shutil_copy2_preserves_metadata():
    """真 shutil.copy2 真保留 mtime"""
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / "src.txt"
        dst = pathlib.Path(d) / "dst.txt"
        src.write_text("data")
        # 改 mtime
        import os, time
        old_time = time.time() - 10000
        os.utime(src, (old_time, old_time))
        shutil.copy2(str(src), str(dst))
        # mtime 保留 (close)
        assert abs(dst.stat().st_mtime - old_time) < 5


def test_shutil_copytree():
    """真 shutil.copytree 真递归"""
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / "src"
        src.mkdir()
        (src / "a.txt").write_text("A")
        (src / "sub").mkdir()
        (src / "sub" / "b.txt").write_text("B")
        dst = pathlib.Path(d) / "dst"
        shutil.copytree(str(src), str(dst))
        assert (dst / "a.txt").read_text() == "A"
        assert (dst / "sub" / "b.txt").read_text() == "B"


def test_shutil_rmtree():
    """真 shutil.rmtree 真递归删"""
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d) / "rm"
        root.mkdir()
        (root / "sub").mkdir()
        (root / "sub" / "file.txt").write_text("X")
        (root / "a.txt").write_text("A")
        shutil.rmtree(str(root))
        assert not root.exists()


def test_shutil_disk_usage():
    """真 shutil.disk_usage 真 OS stat"""
    with tempfile.TemporaryDirectory() as d:
        usage = shutil.disk_usage(d)
        # total > 0 必有 (mount 真)
        assert usage.total > 0
        # used 和 free 至少一个 > 0
        assert usage.used > 0 or usage.free > 0
        # 字段类型
        assert isinstance(usage.total, int)
        assert isinstance(usage.free, int)
        assert isinstance(usage.used, int)

def test_shutil_which():
    """真 shutil.which 真 PATH 查找"""
    python_path = shutil.which("python3")
    assert python_path is not None
    assert os.path.isfile(python_path)
    # 不存在
    assert shutil.which("non_existent_command_xyz_abc") is None


# ======================== tempfile ========================
def test_tempfile_mkdtemp():
    """真 tempfile.mkdtemp 真 OS 目录"""
    d = tempfile.mkdtemp(prefix="forgemind_")
    try:
        assert os.path.isdir(d)
        # prefix 保留
        assert "forgemind_" in d
        # 真写文件
        f = pathlib.Path(d) / "test.txt"
        f.write_text("hello")
        assert f.read_text() == "hello"
    finally:
        shutil.rmtree(d)


def test_tempfile_named_temporary_file():
    """真 NamedTemporaryFile 真可读可写"""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as f:
        f.write("data line 1\n")
        f.write("data line 2\n")
        path = f.name
    try:
        content = pathlib.Path(path).read_text()
        assert "data line 1" in content
        assert "data line 2" in content
    finally:
        os.unlink(path)


def test_tempfile_spooled_temporary_file():
    """真 SpooledTemporaryFile 真 spill 落盘"""
    with tempfile.SpooledTemporaryFile(max_size=100, mode="w+") as f:
        f.write("small")
        # 还在内存 (未超 max_size)
        assert f._rolled == False
        # 写超 max_size
        f.write("X" * 200)
        f.seek(0)
        # 应 spill 到 disk
        assert f._rolled == True
        content = f.read()
        assert content.startswith("small")


# ======================== uuid ========================
def test_uuid_version4():
    """真 uuid4 真随机"""
    u1 = uuid.uuid4()
    u2 = uuid.uuid4()
    # 永不重
    assert u1 != u2
    # version 4
    assert u1.version == 4
    # 标准格式
    assert str(u1).count("-") == 4
    assert len(str(u1)) == 36


def test_uuid_version1():
    """真 uuid1 真带时间戳"""
    u1 = uuid.uuid1()
    assert u1.version == 1
    # 真有时间戳
    assert u1.time > 0


def test_uuid_uuid5_namespace():
    """真 uuid5 真 deterministic"""
    ns = uuid.NAMESPACE_DNS
    # 同样输入同输出
    u1 = uuid.uuid5(ns, "python.org")
    u2 = uuid.uuid5(ns, "python.org")
    assert u1 == u2
    # 同样 ns 同样 input
    u3 = uuid.uuid5(ns, "python.com")
    assert u1 != u3
    # 真 32 hex
    assert len(u1.hex) == 32


def test_uuid_namespace_const():
    """真 uuid namespace 常量"""
    assert uuid.NAMESPACE_DNS == uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    assert uuid.NAMESPACE_URL == uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")
    assert uuid.NAMESPACE_OID == uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")
    assert uuid.NAMESPACE_X500 == uuid.UUID("6ba7b814-9dad-11d1-80b4-00c04fd430c8")


# ======================== fileinput ========================
def test_fileinput_iterate():
    """真 fileinput 真迭代文件"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("line1\nline2\nline3\n")
        path = f.name
    try:
        lines = []
        for line in fileinput.input(path):
            lines.append(line.rstrip())
        assert lines == ["line1", "line2", "line3"]
    finally:
        os.unlink(path)


def test_fileinput_inplace_rewrite():
    """真 fileinput inplace 重写真文件"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("apple\nbanana\ncherry\n")
        path = f.name
    try:
        # 加 prefix
        for line in fileinput.input(path, inplace=True):
            print("fruit_" + line, end="")
        content = pathlib.Path(path).read_text()
        assert "fruit_apple" in content
        assert "fruit_banana" in content
    finally:
        os.unlink(path)
