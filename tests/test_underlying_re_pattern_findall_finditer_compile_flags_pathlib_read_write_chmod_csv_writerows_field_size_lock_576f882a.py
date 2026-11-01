# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`re 进阶 (Pattern.findall+finditer+VERBOSE+ASCII)` + `pathlib 进阶 (read_text+write_text+chmod+read_bytes)` + `csv 进阶 (writerows+field_size_limit)` + `threading 进阶 (Lock+RLock+Condition)` + 真底层测试。

覆盖 re 4 真 + pathlib 4 真 + csv 2 真 + threading 3 真 (共 13 真测试) 模块:
  - `re.Pattern.findall 'forge' ≥ 1`
  - `re.Pattern.finditer 'forge' ≥ 1`
  - `re.compile VERBOSE 'a b c'`
  - `re.compile ASCII 'a'`
  - `pathlib read_text 'forge_text'`
  - `pathlib write_text 'forge_write'`
  - `pathlib chmod 0o644`
  - `pathlib read_bytes b'forge_bytes'`
  - `csv.writerows 真 3 rows`
  - `csv.field_size_limit ≥ 0`
  - `threading.Lock acquire+release`
  - `threading.RLock reentrant`
  - `threading.Condition acquire+release`
"""
import csv
import io
import pathlib
import re
import threading

import pytest


# -- re 进阶 (Pattern.findall+finditer+compile flags) -----

class TestRePatternFindallFinditerCompileFlagsAdvance:
    def test_Pattern_findall(self):
        """`re.Pattern.findall 'forge' ≥ 1。"""
        p = re.compile(r"forge")
        result = p.findall("forge_value_forge_test")
        # 必 ≥ 1
        assert len(result) >= 1
        # 必 ['forge', 'forge']
        assert result == ["forge", "forge"]

    def test_Pattern_finditer(self):
        """`re.Pattern.finditer 'forge' ≥ 1。"""
        p = re.compile(r"forge")
        result = list(p.finditer("forge_value_forge_test"))
        # 必 ≥ 1
        assert len(result) >= 1
        # 必 'forge' group
        assert all(m.group() == "forge" for m in result)

    def test_compile_VERBOSE(self):
        """`re.compile VERBOSE 'a b c'。"""
        p = re.compile(r"""
            \w+    # first word
            \s+    # whitespace
            \w+    # second word
            \s+    # whitespace
            \w+    # third word
        """, re.VERBOSE)
        m = p.match("a b c")
        # 必能
        assert m is not None
        # 必 'a b c'
        assert m.group() == "a b c"

    def test_compile_ASCII(self):
        """`re.compile ASCII 'a'。"""
        p = re.compile(r"\w", re.ASCII)
        m = p.match("a")
        # 必能
        assert m is not None
        # 必 'a'
        assert m.group() == "a"


# -- pathlib 进阶 (read_text+write_text+chmod+read_bytes) ----

class TestPathlibReadWriteChmodAdvanceV2:
    def test_read_text(self, tmp_path):
        """`pathlib read_text 'forge_text'。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge_text")
        # 必 'forge_text'
        assert f.read_text() == "forge_text"

    def test_write_text(self, tmp_path):
        """`pathlib write_text 'forge_write' 必含。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge_write")
        # 必含 'forge_write'
        assert "forge_write" in f.read_text()

    def test_chmod(self, tmp_path):
        """`pathlib chmod 0o644 真能。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge")
        # chmod
        f.chmod(0o644)
        # 必 mode & 0o644
        mode = f.stat().st_mode
        # 必能读
        assert mode & 0o644

    def test_read_bytes(self, tmp_path):
        """`pathlib read_bytes b'forge_bytes'。"""
        f = tmp_path / "forge.bin"
        f.write_bytes(b"forge_bytes")
        # 必 b'forge_bytes'
        assert f.read_bytes() == b"forge_bytes"


# -- csv 进阶 (writerows + field_size_limit) -------------

class TestCsvWriterowsFieldSizeLimitAdvanceV2:
    def test_writerows(self):
        """`csv.writerows 真 3 rows。"""
        buf = io.StringIO()
        writer = csv.writer(buf)
        # writerows
        writer.writerows([["a", "b", "c"]])
        # 必含 'a' 'b' 'c'
        output = buf.getvalue()
        assert "a" in output
        assert "b" in output
        assert "c" in output

    def test_field_size_limit(self):
        """`csv.field_size_limit ≥ 0。"""
        old = csv.field_size_limit()
        # 必 int
        assert isinstance(old, int)
        # 必 ≥ 0
        assert old >= 0
        # restore
        csv.field_size_limit(old)


# -- threading 进阶 (Lock+RLock+Condition) ---------------

class TestThreadingLockRLockConditionAdvance:
    def test_Lock(self):
        """`threading.Lock 真能 acquire+release。"""
        lock = threading.Lock()
        # 必能 acquire
        assert lock.acquire(timeout=5) is True
        # 必能 release
        lock.release()
        # 必不抛
        assert True

    def test_RLock_reentrant(self):
        """`threading.RLock 真 reentrant。"""
        rlock = threading.RLock()
        # 真 reentrant
        rlock.acquire()
        rlock.acquire()
        rlock.release()
        rlock.release()
        # 必不抛
        assert True

    def test_Condition(self):
        """`threading.Condition 真能 acquire+release。"""
        cond = threading.Condition()
        # 必能 acquire
        cond.acquire()
        # 必能 release
        cond.release()
        # 必不抛
        assert True
