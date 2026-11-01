# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`time 进阶 (gmtime+localtime+asctime+ctime 真)` + `uuid 进阶 (uuid3+uuid5+getnode 真)` + `platform 进阶 (system+release+version+machine 真)` + 真底层测试。

覆盖 time 4 真 + uuid 3 真 + platform 4 真 (共 11 真测试) 模块:
  - `time.gmtime 2026-01-01`
  - `time.localtime tm_year ≥ 2020`
  - `time.asctime weekday`
  - `time.ctime weekday`
  - `uuid.uuid3 version=3`
  - `uuid.uuid5 version=5`
  - `uuid.getnode int ≥ 0`
  - `platform.system 非空`
  - `platform.release 非空`
  - `platform.version 非空`
  - `platform.machine 非空`
"""
import platform
import time
import uuid

import pytest


# -- time 进阶 (gmtime+localtime+asctime+ctime) -------

class TestTimeAdvanceV4:
    def test_gmtime(self):
        """`time.gmtime 2026-01-01。"""
        t = time.gmtime(1767225600)
        assert t.tm_year == 2026
        assert t.tm_mon == 1
        assert t.tm_mday == 1

    def test_localtime(self):
        """`time.localtime tm_year ≥ 2020。"""
        t = time.localtime()
        assert t.tm_year >= 2020

    def test_asctime(self):
        """`time.asctime weekday。"""
        s = time.asctime()
        assert isinstance(s, str)
        assert s[:3] in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    def test_ctime(self):
        """`time.ctime weekday。"""
        s = time.ctime()
        assert isinstance(s, str)
        assert s[:3] in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


# -- uuid 进阶 (uuid3+uuid5+getnode) -------------------

class TestUuidAdvanceV3:
    def test_uuid3(self):
        """`uuid.uuid3 version=3。"""
        u = uuid.uuid3(uuid.NAMESPACE_DNS, "forge.example.com")
        assert len(str(u)) == 36
        assert u.version == 3

    def test_uuid5(self):
        """`uuid.uuid5 version=5。"""
        u = uuid.uuid5(uuid.NAMESPACE_DNS, "forge.example.com")
        assert len(str(u)) == 36
        assert u.version == 5

    def test_getnode(self):
        """`uuid.getnode int ≥ 0。"""
        node = uuid.getnode()
        assert isinstance(node, int)
        assert node >= 0


# -- platform 进阶 (system+release+version+machine) -----

class TestPlatformAdvanceV3:
    def test_system(self):
        """`platform.system 非空。"""
        s = platform.system()
        assert isinstance(s, str)
        assert len(s) > 0

    def test_release(self):
        """`platform.release 非空。"""
        s = platform.release()
        assert isinstance(s, str)
        assert len(s) > 0

    def test_version(self):
        """`platform.version 非空。"""
        s = platform.version()
        assert isinstance(s, str)
        assert len(s) > 0

    def test_machine(self):
        """`platform.machine 非空。"""
        s = platform.machine()
        assert isinstance(s, str)
        assert len(s) > 0
