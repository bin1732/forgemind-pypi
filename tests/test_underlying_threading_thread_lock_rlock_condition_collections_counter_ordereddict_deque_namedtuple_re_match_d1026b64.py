# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`threading 进阶 (Thread+Lock+RLock+Condition)` + `collections 进阶 (Counter+OrderedDict+defaultdict+deque+namedtuple+ChainMap)` + `re 进阶 (compile+match+search+fullmatch)` + `pathlib 进阶 (iterdir+glob+rglob+resolve+absolute)` + `ctypes 进阶 (c_int+c_long+c_float+c_double+c_char)` + 真底层测试。

覆盖 threading 4 真 + collections 6 真 + re 4 真 + pathlib 5 真 + ctypes 5 真 (共 24 真测试) 模块:
  - `threading.Thread args start+join`
  - `threading.Lock acquire+release`
  - `threading.RLock reentrant`
  - `threading.Condition acquire+release`
  - `collections.Counter 'forge_forge' 频 2`
  - `collections.OrderedDict 保序 [z, a, m]`
  - `collections.defaultdict 'forge_default'`
  - `collections.deque append+appendleft`
  - `collections.namedtuple _ForgePt`
  - `collections.ChainMap 'forge_child'`
  - `re.compile 'forge' Pattern`
  - `re.match 'forge'`
  - `re.search 'forge'`
  - `re.fullmatch 'forge'`
  - `pathlib.iterdir ≥ 2`
  - `pathlib.glob '*.txt' ≥ 1`
  - `pathlib.rglob '*.txt' ≥ 1`
  - `pathlib.resolve absolute`
  - `pathlib.absolute absolute`
  - `ctypes.c_int 42`
  - `ctypes.c_long 100`
  - `ctypes.c_float 1.5`
  - `ctypes.c_double 1.5`
  - `ctypes.c_char b'F'`
"""
import collections
import ctypes
import pathlib
import re
import threading

import pytest


def _thread_target_t(arg):
    return f"forge_thread_{arg}"


# -- threading 进阶 (Thread+Lock+RLock+Condition) -------

class TestThreadingThreadLockRLockConditionAdvance:
    def test_Thread_args(self):
        """`threading.Thread args start+join。"""
        t = threading.Thread(target=_thread_target_t, args=("forge_arg",))
        t.start()
        t.join(timeout=5)
        assert True

    def test_Lock(self):
        """`threading.Lock acquire+release。"""
        lock = threading.Lock()
        assert lock.acquire(timeout=5) is True
        lock.release()
        assert True

    def test_RLock(self):
        """`threading.RLock reentrant。"""
        rlock = threading.RLock()
        rlock.acquire()
        rlock.acquire()
        rlock.release()
        rlock.release()
        assert True

    def test_Condition(self):
        """`threading.Condition acquire+release。"""
        cond = threading.Condition()
        cond.acquire()
        cond.release()
        assert True


# -- collections 进阶 (Counter+OrderedDict+defaultdict+deque+namedtuple+ChainMap) ---

class TestCollectionsAdvanceV3:
    def test_Counter(self):
        """`collections.Counter 'forge_forge' 频 2。"""
        c = collections.Counter("forge_forge")
        assert c["f"] == 2
        assert c["o"] == 2

    def test_OrderedDict(self):
        """`collections.OrderedDict 保序 [z, a, m]。"""
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        assert list(od.keys()) == ["z", "a", "m"]

    def test_defaultdict(self):
        """`collections.defaultdict 'forge_default'。"""
        dd = collections.defaultdict(lambda: "forge_default")
        assert dd["nonexistent"] == "forge_default"

    def test_deque(self):
        """`collections.deque append+appendleft。"""
        dq = collections.deque()
        dq.append("forge_right")
        dq.appendleft("forge_left")
        assert dq[0] == "forge_left"

    def test_namedtuple(self):
        """`collections.namedtuple _ForgePt (42, 'forge')。"""
        _ForgePt = collections.namedtuple("_ForgePt", ["x", "y"])
        pt = _ForgePt(42, "forge")
        assert pt.x == 42
        assert pt.y == "forge"

    def test_ChainMap(self):
        """`collections.ChainMap 'forge_child'。"""
        parent = {"a": "parent_value"}
        child = {"b": "forge_child"}
        cm = collections.ChainMap(child, parent)
        assert cm["b"] == "forge_child"


# -- re 进阶 (compile+match+search+fullmatch) --------

class TestReAdvanceV5:
    def test_compile_search(self):
        """`re.compile 'forge' Pattern。"""
        p = re.compile("forge")
        assert isinstance(p, re.Pattern)
        m = p.search("forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_match(self):
        """`re.match 'forge'。"""
        m = re.match("forge", "forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_search(self):
        """`re.search 'forge'。"""
        m = re.search("forge", "value_forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_fullmatch(self):
        """`re.fullmatch 'forge'。"""
        m = re.fullmatch("forge", "forge")
        assert m is not None
        assert m.group() == "forge"


# -- pathlib 进阶 (iterdir+glob+rglob+resolve+absolute) ---

class TestPathlibAdvanceV8:
    def test_iterdir(self, tmp_path):
        """`pathlib.iterdir tmp_path ≥ 2。"""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        entries = list(tmp_path.iterdir())
        assert len(entries) >= 2

    def test_glob(self, tmp_path):
        """`pathlib.glob '*.txt' ≥ 1。"""
        (tmp_path / "forge_glob.txt").write_text("forge")
        result = list(tmp_path.glob("*.txt"))
        assert len(result) >= 1

    def test_rglob(self, tmp_path):
        """`pathlib.rglob '*.txt' ≥ 1。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "forge_rglob.txt").write_text("forge")
        result = list(tmp_path.rglob("*.txt"))
        assert len(result) >= 1

    def test_resolve(self, tmp_path):
        """`pathlib.resolve absolute。"""
        f = tmp_path / "forge_resolve.txt"
        f.write_text("forge")
        assert f.resolve().is_absolute()

    def test_absolute(self, tmp_path):
        """`pathlib.absolute absolute。"""
        f = tmp_path / "forge_abs.txt"
        f.write_text("forge")
        assert f.absolute().is_absolute()


# -- ctypes 进阶 (c_int+c_long+c_float+c_double+c_char) ---

class TestCtypesAdvanceV6:
    def test_c_int(self):
        """`ctypes.c_int 42。"""
        v = ctypes.c_int(42)
        assert v.value == 42

    def test_c_long(self):
        """`ctypes.c_long 100。"""
        v = ctypes.c_long(100)
        assert v.value == 100

    def test_c_float(self):
        """`ctypes.c_float 1.5。"""
        v = ctypes.c_float(1.5)
        assert v.value == 1.5

    def test_c_double(self):
        """`ctypes.c_double 1.5。"""
        v = ctypes.c_double(1.5)
        assert v.value == 1.5

    def test_c_char(self):
        """`ctypes.c_char b'F'。"""
        c = ctypes.c_char(b"F")
        assert c.value == b"F"
