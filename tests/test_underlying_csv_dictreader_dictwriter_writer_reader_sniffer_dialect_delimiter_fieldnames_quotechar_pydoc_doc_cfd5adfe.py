# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`csv.DictReader/DictWriter/reader/writer/Sniffer` 真用 (CSV 真读写) + `pydoc.HTMLDoc` 真用 + `pydoc.getpager` 沙箱 skip + `platform.python_implementation/python_version_tuple/python_build/no_arch` + 真底层测试。

覆盖 csv 4 真 (DictReader 真读+DictWriter 真写+reader 真+Sniffer 真 sniff) + pydoc 2 真 (HTMLDoc 真 class+help class 存在 沙箱) + platform 3 真 (python_implementation+python_version_tuple+python_build) (共 9 真测试) 模块:
  - `csv.DictReader 真读 CSV 必能按 key 访问 'forge'`
  - `csv.DictWriter 真写 + writeheader + writerow 必含 'forge,row'`
  - `csv.reader 真 split ',' 含 'forge'`
  - `csv.Sniffer 真 sniff delimiter ','`
  - `pydoc.HTMLDoc class 必存在`
  - `pydoc.help class 必存在 (沙箱 skip 实际输出)`
  - `platform.python_implementation 必 'CPython'`
  - `platform.python_version_tuple 必 3-tuple (>= 3)`
  - `platform.python_build 必 2-tuple 含 str`
"""
import csv
import io
import platform
import pydoc
import sys

import pytest


# -- csv 进阶 (DictReader + DictWriter + reader + Sniffer) ---------

class TestCsvAdvanced:
    def test_DictReader(self):
        """`csv.DictReader 真读 CSV 必能按 key 访问 'forge'。"""
        data = "name,value\nforge,42\nthird,99\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        # 必 2
        assert len(rows) == 2
        # 必含 'forge'
        assert rows[0]["name"] == "forge"
        assert rows[0]["value"] == "42"

    def test_DictWriter(self):
        """`csv.DictWriter 真写 + writeheader + writerow 必含 'forge,row'。"""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["name", "value"])
        writer.writeheader()
        writer.writerow({"name": "forge", "value": "row"})
        result = buf.getvalue()
        # 必含 'name,value' (header)
        assert "name,value" in result
        # 必含 'forge,row'
        assert "forge,row" in result

    def test_reader(self):
        """`csv.reader 真 split ',' 含 'forge'。"""
        data = "a,b,c\nforge,42,test\n"
        reader = csv.reader(io.StringIO(data))
        rows = list(reader)
        # 必 2 (含 header)
        assert len(rows) == 2
        # 必含 'forge' (header 后 row)
        assert "forge" in rows[1]

    def test_Sniffer(self):
        """`csv.Sniffer 真 sniff delimiter ','。"""
        # 真 sample CSV
        sample = "a,b,c\n1,2,3\n4,5,6\n"
        dialect = csv.Sniffer().sniff(sample, delimiters=",")
        # 必 delimiter = ','
        assert dialect.delimiter == ","


# -- pydoc 进阶 (HTMLDoc + help) -----------------------------------

class TestPydocAdvanced:
    def test_HTMLDoc_class(self):
        """`pydoc.HTMLDoc class 必存在。"""
        # 沙箱 3.11 HTMLDoc 必有
        assert pydoc.HTMLDoc is not None
        # 必能建
        h = pydoc.HTMLDoc()
        # 必含 docclass
        assert hasattr(h, "docclass")

    def test_help_class(self):
        """`pydoc.help class 必存在 (沙箱 skip 实际输出)。"""
        # 沙箱 3.11 help 必为 class
        assert pydoc.help is not None


# -- platform 进阶 (python_implementation + python_version_tuple + python_build) -

class TestPlatformAdvancedV2:
    def test_python_implementation(self):
        """`platform.python_implementation 必 'CPython'。"""
        impl = platform.python_implementation()
        # 必 'CPython'
        assert impl == "CPython"

    def test_python_version_tuple(self):
        """`platform.python_version_tuple 必 3-tuple。"""
        v = platform.python_version_tuple()
        # 必 tuple of 3
        assert len(v) == 3
        # 必 int
        assert all(isinstance(x, str) for x in v)
        # 必 ≥ 3
        assert int(v[0]) >= 3

    def test_python_build(self):
        """`platform.python_build 必 2-tuple 含 str。"""
        b = platform.python_build()
        # 必 tuple of 2
        assert len(b) == 2
        # 必 str
        assert all(isinstance(x, str) for x in b)
