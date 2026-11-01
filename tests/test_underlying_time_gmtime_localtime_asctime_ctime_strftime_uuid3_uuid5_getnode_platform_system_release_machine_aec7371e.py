# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`time` 进阶 (gmtime+localtime+asctime+ctime+strftime 真) + `uuid` 进阶 (uuid3+uuid5+getnode+UUID fields 真) + `platform` 进阶 (system+release+version+machine 真) + `pathlib` 进阶 (read_text+write_text+chmod+read_bytes 真) + 真底层测试。

覆盖 time 4 真 + uuid 4 真 + platform 4 真 + pathlib 4 真 (共 16 真测试) 模块:
  - `time.gmtime 真 (2026,1,1,0,0,0) 含 tm_year=2026`
  - `time.localtime 真 local tm_year ≥ 2020`
  - `time.asctime 真 3-letter weekday`
  - `time.ctime 真当前 3-letter weekday`
  - `time.strftime 真 time.gmtime 2026/01/01`
  - `uuid.uuid3 真 'forge' 必 36 chars + '3' 开头`
  - `uuid.uuid5 真 'forge' 必 36 chars + '5' 开头`
  - `uuid.getnode 真 int ≥ 0`
  - `uuid.UUID fields tuple 6 int`
  - `platform.system 必非空 str`
  - `platform.release 必非空 str`
  - `platform.version 必非空 str`
  - `platform.machine 必非空 str`
  - `pathlib read_text 'forge_text'`
  - `pathlib write_text 'forge_write'`
  - `pathlib chmod 0o644`
  - `pathlib read_bytes b'forge_bytes'`
"""
import os
import pathlib
import platform
import time
import uuid

import pytest


# -- time 进阶 (gmtime+localtime+asctime+ctime+strftime) ---

class TestTimeAdvanceV2:
    def test_gmtime(self):
        """`time.gmtime 真 (2026,1,1,0,0,0) 含 tm_year=2026。"""
        t = time.gmtime(1767225600)
        assert t.tm_year == 2026
        assert t.tm_mon == 1
        assert t.tm_mday == 1

    def test_localtime(self):
        """`time.localtime 真 local tm_year ≥ 2020。"""
        t = time.localtime()
        # 必 tm_year ≥ 2020
        assert t.tm_year >= 2020

    def test_asctime(self):
        """`time.asctime 真 3-letter weekday。"""
        s = time.asctime()
        # 必 str
        assert isinstance(s, str)
        # 必含 3-letter weekday
        assert s[:3] in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    def test_ctime(self):
        """`time.ctime 真当前 3-letter weekday。"""
        s = time.ctime()
        # 必 str
        assert isinstance(s, str)
        # 必含 3-letter weekday
        assert s[:3] in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    def test_strftime(self):
        """`time.strftime 真 time.gmtime 2026/01/01。"""
        t = time.gmtime(1767225600)
        s = time.strftime("%Y/%m/%d", t)
        # 必 '2026/01/01'
        assert s == "2026/01/01"


# -- uuid 进阶 (uuid3+uuid5+getnode+UUID fields) -------------

class TestUuidAdvance:
    def test_uuid3(self):
        """`uuid.uuid3 真 'forge' 必 36 chars + version=3。"""
        u = uuid.uuid3(uuid.NAMESPACE_DNS, "forge.example.com")
        # 必 36 chars
        assert len(str(u)) == 36
        # 必 version=3
        assert u.version == 3
        # 必可 round-trip
        assert uuid.UUID(str(u)) == u

    def test_uuid5(self):
        """`uuid.uuid5 真 'forge' 必 36 chars + version=5。"""
        u = uuid.uuid5(uuid.NAMESPACE_DNS, "forge.example.com")
        # 必 36 chars
        assert len(str(u)) == 36
        # 必 version=5
        assert u.version == 5

    def test_getnode(self):
        """`uuid.getnode 真 int ≥ 0。"""
        node = uuid.getnode()
        # 必 int
        assert isinstance(node, int)
        # 必 ≥ 0
        assert node >= 0

    def test_UUID_fields(self):
        """`uuid.UUID fields tuple 6 int。"""
        u = uuid.uuid4()
        # 必 fields
        f = u.fields
        # 必 tuple 6
        assert len(f) == 6
        # 必 int
        assert all(isinstance(x, int) for x in f)


# -- platform 进阶 (system+release+version+machine) ----------

class TestPlatformAdvance:
    def test_system(self):
        """`platform.system 必非空 str。"""
        s = platform.system()
        # 必非空
        assert isinstance(s, str)
        assert len(s) > 0

    def test_release(self):
        """`platform.release 必非空 str。"""
        s = platform.release()
        # 必非空
        assert isinstance(s, str)
        assert len(s) > 0

    def test_version(self):
        """`platform.version 必非空 str。"""
        s = platform.version()
        # 必非空
        assert isinstance(s, str)
        assert len(s) > 0

    def test_machine(self):
        """`platform.machine 必非空 str。"""
        s = platform.machine()
        # 必非空
        assert isinstance(s, str)
        assert len(s) > 0


# -- pathlib 进阶 (read_text+write_text+chmod+read_bytes) ----

class TestPathlibReadWriteChmodAdvance:
    def test_read_text(self, tmp_path):
        """`pathlib read_text 真 'forge_text' 必 'forge_text'。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge_text")
        # 必 'forge_text'
        assert f.read_text() == "forge_text"

    def test_write_text(self, tmp_path):
        """`pathlib write_text 真 'forge_write' 必含。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge_write")
        # 必含 'forge_write'
        assert "forge_write" in f.read_text()

    def test_chmod(self, tmp_path):
        """`pathlib chmod 真 0o644 必能。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge")
        # chmod
        f.chmod(0o644)
        # 必 mode & 0o644
        mode = f.stat().st_mode
        # 必能读
        assert mode & 0o644

    def test_read_bytes(self, tmp_path):
        """`pathlib read_bytes 真 'forge_bytes' 必 b'forge_bytes'。"""
        f = tmp_path / "forge.bin"
        f.write_bytes(b"forge_bytes")
        # 必 b'forge_bytes'
        assert f.read_bytes() == b"forge_bytes"
