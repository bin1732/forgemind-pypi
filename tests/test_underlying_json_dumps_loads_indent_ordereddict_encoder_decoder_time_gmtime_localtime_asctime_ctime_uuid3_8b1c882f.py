# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`json 进阶 (dumps+loads+indent+OrderedDict+JSONEncoder+JSONDecoder 真)` + `time 进阶 (gmtime+localtime+asctime+ctime 真)` + `uuid 进阶 (uuid3+uuid5+getnode 真)` + `platform 进阶 (system+release+version+machine 真)` + 真底层测试。

覆盖 json 4 真 + time 4 真 + uuid 3 真 + platform 4 真 (共 15 真测试) 模块:
  - `json.dumps indent=2 必含 'forge' '\\n'`
  - `json.loads '{"forge":42}' 必 42`
  - `json OrderedDict round-trip 必等`
  - `json JSONEncoder.encode+JSONDecoder.decode round-trip`
  - `time.gmtime(1767225600) 必 2026-01-01`
  - `time.localtime tm_year ≥ 2020`
  - `time.asctime 3-letter weekday`
  - `time.ctime 3-letter weekday`
  - `uuid.uuid3 version=3`
  - `uuid.uuid5 version=5`
  - `uuid.getnode int ≥ 0`
  - `platform.system 非空 str`
  - `platform.release 非空 str`
  - `platform.version 非空 str`
  - `platform.machine 非空 str`
"""
import collections
import json
import platform
import time
import uuid

import pytest


# -- json 进阶 (dumps+loads+indent+OrderedDict+Encoder+Decoder) ----

class TestJsonAdvanceV2:
    def test_dumps_indent(self):
        """`json.dumps indent=2 必含 'forge' '\\n'。"""
        d = {"name": "forge", "value": 42}
        result = json.dumps(d, indent=2)
        # 必 str
        assert isinstance(result, str)
        # 必含 'name' 'forge' '42'
        assert "name" in result
        assert "forge" in result
        assert "42" in result
        # 必含 '\\n'
        assert "\n" in result

    def test_loads(self):
        """`json.loads '{"forge":42}' 必 42。"""
        data = '{"forge": 42, "name": "value"}'
        result = json.loads(data)
        # 必 dict
        assert isinstance(result, dict)
        # 必 42
        assert result["forge"] == 42
        # 必 'value'
        assert result["name"] == "value"

    def test_OrderedDict_round_trip(self):
        """`json OrderedDict round-trip 必等。"""
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        # dumps 必保序
        encoded = json.dumps(od)
        # loads 必能
        decoded = json.loads(encoded)
        # 必等
        assert decoded == dict(od)
        # 必 3 keys
        assert len(decoded) == 3

    def test_JSONEncoder_decode(self):
        """`json JSONEncoder.encode+JSONDecoder.decode round-trip。"""
        enc = json.JSONEncoder()
        # encode
        encoded = enc.encode({"forge": 42})
        # 必 str
        assert isinstance(encoded, str)
        # 必含 'forge'
        assert "forge" in encoded
        # decode
        decoded = json.JSONDecoder().decode(encoded)
        # 必 dict
        assert decoded["forge"] == 42


# -- time 进阶 (gmtime+localtime+asctime+ctime) -------

class TestTimeAdvanceV3:
    def test_gmtime(self):
        """`time.gmtime(1767225600) 必 2026-01-01。"""
        t = time.gmtime(1767225600)
        assert t.tm_year == 2026
        assert t.tm_mon == 1
        assert t.tm_mday == 1

    def test_localtime(self):
        """`time.localtime tm_year ≥ 2020。"""
        t = time.localtime()
        # 必 tm_year ≥ 2020
        assert t.tm_year >= 2020

    def test_asctime(self):
        """`time.asctime 3-letter weekday。"""
        s = time.asctime()
        # 必 str
        assert isinstance(s, str)
        # 必含 3-letter weekday
        assert s[:3] in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    def test_ctime(self):
        """`time.ctime 3-letter weekday。"""
        s = time.ctime()
        # 必 str
        assert isinstance(s, str)
        # 必含 3-letter weekday
        assert s[:3] in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


# -- uuid 进阶 (uuid3+uuid5+getnode) -------------------

class TestUuidAdvanceV2:
    def test_uuid3(self):
        """`uuid.uuid3 version=3。"""
        u = uuid.uuid3(uuid.NAMESPACE_DNS, "forge.example.com")
        # 必 36 chars
        assert len(str(u)) == 36
        # 必 version=3
        assert u.version == 3

    def test_uuid5(self):
        """`uuid.uuid5 version=5。"""
        u = uuid.uuid5(uuid.NAMESPACE_DNS, "forge.example.com")
        # 必 36 chars
        assert len(str(u)) == 36
        # 必 version=5
        assert u.version == 5

    def test_getnode(self):
        """`uuid.getnode int ≥ 0。"""
        node = uuid.getnode()
        # 必 int
        assert isinstance(node, int)
        # 必 ≥ 0
        assert node >= 0


# -- platform 进阶 (system+release+version+machine) -----

class TestPlatformAdvanceV2:
    def test_system(self):
        """`platform.system 非空 str。"""
        s = platform.system()
        # 必非空
        assert isinstance(s, str)
        assert len(s) > 0

    def test_release(self):
        """`platform.release 非空 str。"""
        s = platform.release()
        # 必非空
        assert isinstance(s, str)
        assert len(s) > 0

    def test_version(self):
        """`platform.version 非空 str。"""
        s = platform.version()
        # 必非空
        assert isinstance(s, str)
        assert len(s) > 0

    def test_machine(self):
        """`platform.machine 非空 str。"""
        s = platform.machine()
        # 必非空
        assert isinstance(s, str)
        assert len(s) > 0
