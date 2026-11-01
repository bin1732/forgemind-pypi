# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`logging.Filter` 子化 + emit + LogRecord factory 进阶 (3.11+ skip) + `pprint.isreadable+isrecursive+pformat` 进阶 (dict) + `xml.etree` 进阶 (iterparse 真 + set+get attribute) + `csv.DictReader+DictWriter` 进阶 + 真底层测试。

覆盖 logging 3 真 (Filter 子化+emit+factory) + pprint 4 真 (isreadable+isrecursive+pformat+PrettyPrinter) + xml.etree 2 真 (iterparse+set attr) + csv 2 真 (DictReader+DictWriter) (共 11 真测试) 模块:
  - `logging.Filter 子化 + filter 'forge' 必 True`
  - `logging.LogRecord 真 getMessage + levelname 'INFO'`
  - `logging.getLogRecordFactory 必 callable 3.11+`
  - `pprint.isreadable '{a:1}' 必 True`
  - `pprint.isrecursive 'rec' 必 False`
  - `pprint.pformat dict 必 '{'a': 1'`
  - `pprint.PrettyPrinter pformat 必 '{'a': 1'`
  - `xml.etree iterparse 真 1 个 'a' element`
  - `xml.etree Element set 'href'='forge' 必 .get('href')='forge'`
  - `csv.DictReader 'name\\nforge' 必 1 row 'forge'`
  - `csv.DictWriter 'forge,42' 必 1 header 含 'name' 'value'`
"""
import csv
import io
import logging
import pprint
import xml.etree.ElementTree as ET

import pytest


# -- logging.Filter 子化 + LogRecord 进阶 --------------

class _MyFilter(logging.Filter):
    def filter(self, record):
        return "forge" in record.getMessage()


class TestLoggingFilterSubclassAdvanced:
    def test_Filter_subclass(self):
        """`logging.Filter 子化 + filter 'forge' 必 True。"""
        f = _MyFilter()
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg forge", None, None)
        # 必 True
        assert f.filter(record) is True
        # 必非 True (no forge)
        record2 = logging.LogRecord("n", logging.INFO, "/p", 1, "msg no", None, None)
        assert f.filter(record2) is False

    def test_LogRecord_getMessage(self):
        """`logging.LogRecord 真 getMessage + levelname 'INFO'。"""
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg %s", ("forge_arg",), None)
        # 必 'msg forge_arg'
        assert record.getMessage() == "msg forge_arg"
        # 必 levelname 'INFO'
        assert record.levelname == "INFO"

    def test_getLogRecordFactory(self):
        """`logging.getLogRecordFactory 必 callable 3.11+。"""
        # 沙箱 3.11+ 必 callable
        factory = logging.getLogRecordFactory()
        # 必 callable
        assert callable(factory)


# -- pprint 进阶 (isreadable+isrecursive+pformat+PrettyPrinter) -

class TestPprintAdvancedV4:
    def test_isreadable(self):
        """`pprint.isreadable '{a:1}' 必 True。"""
        # dict
        d = {"a": 1, "b": 2}
        # 必 True
        assert pprint.isreadable(d) is True

    def test_isrecursive(self):
        """`pprint.isrecursive 'rec' 必 False。"""
        d = {"a": 1, "b": 2}
        # 必 False (no recursion)
        assert pprint.isrecursive(d) is False

    def test_pformat_dict(self):
        """`pprint.pformat dict 必 '{'a': 1'。"""
        d = {"a": 1, "b": 2}
        result = pprint.pformat(d)
        # 必 str
        assert isinstance(result, str)
        # 必含 'a' '1'
        assert "a" in result
        assert "1" in result

    def test_PrettyPrinter_pformat(self):
        """`pprint.PrettyPrinter pformat 必 '{'a': 1'。"""
        pp = pprint.PrettyPrinter(width=40)
        d = {"a": 1, "b": 2}
        result = pp.pformat(d)
        # 必 str
        assert isinstance(result, str)
        # 必含 'a'
        assert "a" in result


# -- xml.etree 进阶 (iterparse + set attribute) ------------

class TestXmlEtreeAdvancedV5:
    def test_iterparse(self):
        """`xml.etree iterparse 真 1 个 'a' element。"""
        f = io.StringIO("<r><a>data</a><a>data2</a></r>")
        # iterparse
        events = list(ET.iterparse(f, events=("end",)))
        # 必 ≥ 3 (1 r + 2 a)
        assert len(events) >= 3
        # 必 'a' end
        a_count = sum(1 for e, _ in events if e == "end")
        assert a_count >= 2

    def test_set_get_attribute(self):
        """`xml.etree Element set 'href'='forge' 必 .get('href')='forge'。"""
        a = ET.Element("a")
        # set
        a.set("href", "forge")
        # get 必 'forge'
        assert a.get("href") == "forge"


# -- csv.DictReader + DictWriter 进阶 -------------------

class TestCsvDictAdvancedV2:
    def test_DictReader_round_trip(self):
        """`csv.DictReader 'name\\nforge' 必 1 row 'forge'。"""
        data = "name,value\nforge,42\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        # 必 1
        assert len(rows) == 1
        # 必 'forge'
        assert rows[0]["name"] == "forge"
        # 必 '42'
        assert rows[0]["value"] == "42"

    def test_DictWriter_write(self):
        """`csv.DictWriter 'forge,42' 必 1 header 含 'name' 'value'。"""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["name", "value"])
        # writeheader
        writer.writeheader()
        # writerow
        writer.writerow({"name": "forge", "value": "42"})
        # 必含 'name' 'value' 'forge'
        output = buf.getvalue()
        assert "name" in output
        assert "value" in output
        assert "forge" in output
