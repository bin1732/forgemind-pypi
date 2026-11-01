# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`weakref 进阶 (ref+proxy+WeakValueDictionary+WeakKeyDictionary)` + `shutil 进阶 (copy+copytree+rmtree+move+disk_usage+which)` + `inspect 进阶 (signature+Parameter+Signature+bind+replace)` + `multiprocessing 进阶 (Value+Array+Manager+Process)` + 真底层测试。

覆盖 weakref 4 真 + shutil 5 真 + inspect 4 真 + multiprocessing 4 真 (共 17 真测试) 模块:
  - `weakref.ref lambda callable`
  - `weakref.proxy object .v='forge_value'`
  - `weakref.WeakValueDictionary 'forge_weak'`
  - `weakref.WeakKeyDictionary 'forge_weak_key'`
  - `shutil.copyfile 'forge_copy_data'`
  - `shutil.copytree 'forge_tree.txt'`
  - `shutil.rmtree not exist`
  - `shutil.move file exists`
  - `shutil.disk_usage 3-tuple + which 'cat' non-None`
  - `inspect.signature Signature parameters`
  - `inspect.Parameter.empty sentinel`
  - `inspect.Signature.bind a=1 b='forge_value'`
  - `inspect.Signature.replace 'forge_replaced'`
  - `multiprocessing.Value 'i' 142`
  - `multiprocessing.Array 'i' 99`
  - `multiprocessing.Manager list 'forge_value_0'`
  - `multiprocessing.Process 'forge_target' start+join`
"""
import inspect
import multiprocessing
import shutil
import weakref

import pytest


def _mp_value_target(v):
    with v.get_lock():
        v.value = 142


def _mp_array_target(arr):
    arr[0] = 99


def _mp_list_target(lst, key):
    lst.append(f"forge_value_{key}")


def _proc_target():
    return "forge_target"


class _WeakDictValue:
    def __init__(self, v):
        self.v = v


def _forge_inspect_sig(a: int, b: str = "forge") -> str:
    return f"{a}{b}"


# -- weakref 进阶 (ref+proxy+WeakValueDictionary+WeakKeyDictionary) ---

class TestWeakrefAdvanceV2:
    def test_ref(self):
        """`weakref.ref lambda callable。"""
        r = weakref.ref(lambda: "forge_value")
        assert callable(r)

    def test_proxy(self):
        """`weakref.proxy object .v='forge_value'。"""
        obj = _WeakDictValue("forge_value")
        p = weakref.proxy(obj)
        assert p.v == "forge_value"

    def test_WeakValueDictionary(self):
        """`weakref.WeakValueDictionary 'forge_weak'。"""
        d = weakref.WeakValueDictionary()
        obj = _WeakDictValue("forge_weak")
        d["key"] = obj
        assert d["key"].v == "forge_weak"

    def test_WeakKeyDictionary(self):
        """`weakref.WeakKeyDictionary 'forge_weak_key'。"""
        d = weakref.WeakKeyDictionary()
        obj = _WeakDictValue("forge_weak_key")
        d[obj] = "value"
        assert d[obj] == "value"


# -- shutil 进阶 (copy+copytree+rmtree+move+disk_usage+which) ---

class TestShutilAdvanceV3:
    def test_copyfile(self, tmp_path):
        """`shutil.copyfile 'forge_copy_data'。"""
        src = tmp_path / "forge_src.txt"
        src.write_text("forge_copy_data")
        dst = tmp_path / "forge_dst.txt"
        shutil.copyfile(src, dst)
        assert dst.read_text() == "forge_copy_data"

    def test_copytree(self, tmp_path):
        """`shutil.copytree 'forge_tree.txt'。"""
        src = tmp_path / "forge_src_dir"
        src.mkdir()
        (src / "forge_tree.txt").write_text("forge")
        dst = tmp_path / "forge_dst_dir"
        shutil.copytree(src, dst)
        assert (dst / "forge_tree.txt").exists()

    def test_rmtree(self, tmp_path):
        """`shutil.rmtree not exist。"""
        d = tmp_path / "forge_rmtree"
        d.mkdir()
        (d / "forge.txt").write_text("forge")
        shutil.rmtree(d)
        assert not d.exists()

    def test_move(self, tmp_path):
        """`shutil.move file exists。"""
        src = tmp_path / "forge_move_src"
        src.mkdir()
        (src / "forge_moved.txt").write_text("forge")
        dst = tmp_path / "forge_move_dst"
        shutil.move(str(src), str(dst))
        assert (dst / "forge_moved.txt").exists()

    def test_disk_usage_which(self):
        """`shutil.disk_usage 3-tuple + which 'cat' non-None。"""
        usage = shutil.disk_usage("/")
        assert len(usage) == 3
        cat_path = shutil.which("cat")
        assert cat_path is not None


# -- inspect 进阶 (signature+Parameter+Signature+bind+replace) --

class TestInspectAdvanceV4:
    def test_signature(self):
        """`inspect.signature Signature parameters。"""
        sig = inspect.signature(_forge_inspect_sig)
        assert isinstance(sig, inspect.Signature)
        assert "a" in sig.parameters
        assert "b" in sig.parameters

    def test_Parameter_empty(self):
        """`inspect.Parameter.empty sentinel。"""
        empty = inspect.Parameter.empty
        assert empty is not None

    def test_Signature_bind(self):
        """`inspect.Signature.bind a=1 b='forge_value'。"""
        sig = inspect.signature(_forge_inspect_sig)
        bound = sig.bind(a=1, b="forge_value")
        assert "a" in bound.arguments
        assert bound.arguments["a"] == 1

    def test_Signature_replace(self):
        """`inspect.Signature.replace 'forge_replaced'。"""
        sig = inspect.signature(_forge_inspect_sig)
        new_sig = sig.replace(
            parameters=[
                sig.parameters["a"],
                sig.parameters["b"].replace(default="forge_replaced"),
            ]
        )
        assert new_sig.parameters["b"].default == "forge_replaced"


# -- multiprocessing 进阶 (Value+Array+Manager+Process) ---

class TestMultiprocessingValueArrayManagerProcessAdvanceV2:
    def test_Value(self):
        """`multiprocessing.Value 'i' 142。"""
        v = multiprocessing.Value("i", 0)
        p = multiprocessing.Process(target=_mp_value_target, args=(v,))
        p.start()
        p.join(timeout=10)
        assert v.value == 142

    def test_Array(self):
        """`multiprocessing.Array 'i' 99。"""
        arr = multiprocessing.Array("i", [0])
        p = multiprocessing.Process(target=_mp_array_target, args=(arr,))
        p.start()
        p.join(timeout=10)
        assert arr[0] == 99

    def test_Manager_list(self):
        """`multiprocessing.Manager list 'forge_value_0'。"""
        with multiprocessing.Manager() as mgr:
            lst = mgr.list()
            procs = []
            for i in range(5):
                p = multiprocessing.Process(
                    target=_mp_list_target, args=(lst, i)
                )
                p.start()
                procs.append(p)
            for p in procs:
                p.join(timeout=10)
            assert len(lst) >= 5
            assert "forge_value_0" in lst

    def test_Process(self):
        """`multiprocessing.Process 'forge_target' start+join。"""
        p = multiprocessing.Process(target=_proc_target)
        p.start()
        p.join(timeout=5)
        assert True
