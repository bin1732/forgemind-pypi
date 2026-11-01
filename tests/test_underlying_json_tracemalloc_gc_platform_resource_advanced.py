# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`json` 进阶 + `tracemalloc` 进阶 + `gc` 进阶 + `platform` 进阶 + `resource` 真底层测试。

覆盖 JSON / 内存追踪 / 垃圾回收 / 平台 / 资源限制模块:
  - `json.dumps 中文 + ensure_ascii=False` 真返原文
  - `json.dumps + indent=2` 真格式化
  - `json.dumps + sort_keys=True` 真排序
  - `json.dump(obj, file)` 真写文件
  - `json.load(open())` 真读
  - `json.JSONEncoder().encode` 真返 string
  - `json.JSONDecodeError` 真抛
  - `tracemalloc.get_traced_memory()` 返 (current, peak)
  - `tracemalloc.Snapshot.statistics('filename')` 真按 file 分组
  - `tracemalloc.Snapshot.compare_to(other, 'lineno')` 真 diff
  - `gc.isenabled() / disable / enable` 状态机
  - `gc.get_objects() 返 list`
  - `gc.get_referents(obj)` 返 referent objects
  - `gc.get_threshold() / set_threshold` 真设
  - `platform.uname()` 真返 named tuple
  - `platform.freedesktop_os_release()` Linux 返 dict
  - `resource.RLIMIT_NOFILE getrlimit` 真 (soft, hard) tuple
  - `resource.getrlimit/setrlimit` 真 round-trip
  - `resource.RLIMIT_*` 是真 int
"""
import gc
import io
import json
import os
import platform
import resource
import tempfile
import tracemalloc

import pytest


# -- json 进阶 ----------------------------------------------------------------

class TestJsonAdvanced:
    def test_dumps_chinese_ensure_ascii(self):
        """`json.dumps 中文 + ensure_ascii=False` 真返原文。"""
        out = json.dumps({"name": "中文", "val": 42}, ensure_ascii=False)
        # ensure_ascii=False 必保留中文
        assert "中文" in out, f"ensure_ascii=False 应保留 '中文',实际 {out!r}"

    def test_dumps_indent(self):
        """`json.dumps + indent=2` 真格式化多行。"""
        out = json.dumps({"a": 1, "b": 2}, indent=2)
        assert "\n" in out
        # 必含 'a' 和 'b'
        assert '"a"' in out
        assert '"b"' in out

    def test_dumps_sort_keys(self):
        """`json.dumps + sort_keys=True` 真按 key 排序。"""
        out = json.dumps({"b": 1, "a": 2, "c": 3}, sort_keys=True)
        # 'a' 应在 'b' 之前
        assert out.index('"a"') < out.index('"b"'), (
            f"sort_keys=True 应按序,实际 {out!r}"
        )

    def test_dump_load_file(self):
        """`json.dump + json.load` 真文件 round-trip。"""
        data = {"forge": [1, 2, 3], "active": True, "n": None}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.json")
            with open(path, "w") as f:
                json.dump(data, f)
            with open(path) as f:
                loaded = json.load(f)
        assert loaded == data

    def test_JSONEncoder_encode(self):
        """`json.JSONEncoder().encode` 真返 string。"""
        s = json.JSONEncoder().encode({"a": 1})
        assert isinstance(s, str)
        assert '"a"' in s

    def test_JSONDecodeError(self):
        """`json.loads('invalid')` 真抛 JSONDecodeError。"""
        with pytest.raises(json.JSONDecodeError):
            json.loads("{not valid json}")


# -- tracemalloc 进阶 ---------------------------------------------------------

class TestTracemallocAdvancedV2:
    def test_get_traced_memory_tuple(self):
        """`tracemalloc.get_traced_memory()` 真返 (current, peak) tuple。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        try:
            current, peak = tracemalloc.get_traced_memory()
            assert isinstance(current, int) and current >= 0
            assert isinstance(peak, int) and peak >= current
        finally:
            tracemalloc.stop()

    def test_snapshot_statistics_by_filename(self):
        """`Snapshot.statistics('filename')` 真按 file 分组。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        try:
            # 分配一些内存
            data = [i for i in range(1000)]
            snap = tracemalloc.take_snapshot()
            stats = snap.statistics("filename")
            # 必 ≥ 1 个 stat
            assert len(stats) >= 1
            # 第一个 stat 必是 _Stats 对象
            assert hasattr(stats[0], "size")
            assert hasattr(stats[0], "traceback")
            del data
        finally:
            tracemalloc.stop()

    def test_snapshot_compare(self):
        """`Snapshot.compare_to(other, 'lineno')` 真 diff。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        try:
            snap1 = tracemalloc.take_snapshot()
            # 分配内存
            data = [i for i in range(10000)]
            snap2 = tracemalloc.take_snapshot()
            diffs = snap2.compare_to(snap1, "lineno")
            # 至少有一些 diff
            assert len(diffs) >= 1
            del data
        finally:
            tracemalloc.stop()


# -- gc 进阶 ------------------------------------------------------------------

class TestGcAdvanced:
    def test_isenabled(self):
        """`gc.isenabled()` 真返 bool。"""
        v = gc.isenabled()
        assert isinstance(v, bool)
        # 默认 True
        assert v is True

    def test_enable_disable(self):
        """`gc.disable + enable` 状态机。"""
        saved = gc.isenabled()
        try:
            gc.disable()
            assert gc.isenabled() is False
            gc.enable()
            assert gc.isenabled() is True
        finally:
            if saved:
                gc.enable()
            else:
                gc.disable()

    def test_get_objects(self):
        """`gc.get_objects()` 真返 list。"""
        objs = gc.get_objects()
        assert isinstance(objs, list)
        assert len(objs) > 0

    def test_get_referents(self):
        """`gc.get_referents(obj)` 真返 referent values。"""
        inner = [1, 2, 3]
        outer = {"key": inner}
        refs = gc.get_referents(outer)
        # 必含 inner (作为 value)
        assert inner in refs
        # get_referents 返 list of referent objects
        assert isinstance(refs, list)

    def test_get_set_threshold(self):
        """`gc.get_threshold/set_threshold` 真设。"""
        t = gc.get_threshold()
        assert isinstance(t, tuple) and len(t) == 3
        # 设为 (700, 10, 10),然后读回
        gc.set_threshold(700, 10, 10)
        t2 = gc.get_threshold()
        assert t2 == (700, 10, 10)
        # 恢复默认
        gc.set_threshold(*t)


# -- platform 进阶 ------------------------------------------------------------

class TestPlatformAdvanced:
    def test_uname(self):
        """`platform.uname()` 真返 named tuple 5 字段。"""
        u = platform.uname()
        assert hasattr(u, "system")
        assert hasattr(u, "node")
        assert hasattr(u, "release")
        assert hasattr(u, "version")
        assert hasattr(u, "machine")
        assert u.system in ("Linux", "Darwin", "Windows")

    def test_freedesktop_os_release(self):
        """`platform.freedesktop_os_release()` Linux 真返 dict。"""
        try:
            r = platform.freedesktop_os_release()
        except (OSError, AttributeError):
            pytest.skip("freedesktop_os_release 不可用")
        assert isinstance(r, dict)
        # 必含 'NAME' (Linux)
        assert "NAME" in r or "ID" in r


# -- resource -----------------------------------------------------------------

class TestResource:
    def test_RLIMIT_constants(self):
        """`RLIMIT_*` 是真 int。"""
        for name in ("RLIMIT_NOFILE", "RLIMIT_NPROC", "RLIMIT_AS"):
            if hasattr(resource, name):
                assert isinstance(getattr(resource, name), int)

    def test_getrlimit_no(self):
        """`resource.getrlimit(RLIMIT_NOFILE)` 真返 (soft, hard) tuple。"""
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        assert isinstance(soft, int) and soft > 0
        assert isinstance(hard, int) and hard >= soft

    def test_setrlimit_round_trip(self):
        """`setrlimit` 真写回生效。"""
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        try:
            # 设一个不超过 hard 的值
            new_soft = max(hard - 1, 1) if hard > 0 else soft
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
            soft2, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
            assert soft2 == new_soft, (
                f"setrlimit 应生效,期望 {new_soft},实际 {soft2}"
            )
        finally:
            # 恢复
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
            except (ValueError, OSError):
                pass
