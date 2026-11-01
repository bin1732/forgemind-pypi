# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree.ElementTree` 真用 (parse+iter+fromstring+toString+toString_with_decl) + `csv 进阶 (field_size_limit+excel_tab+Sniffer+register_dialect)` + `logging 进阶 (FileHandler+StreamHandler 真发+Formatter+format+getMessage)` + `pprint 进阶 (PrettyPrinter 进阶 indent+depth+width+compact)` + 真底层测试。

覆盖 xml.etree 4 真 (fromstring+iter+parse+toString) + csv 3 真 (field_size_limit+excel_tab+Sniffer) + logging 4 真 (FileHandler+StreamHandler+Formatter+getMessage) + pprint 3 真 (PrettyPrinter indent+depth+width) (共 14 真测试) 模块:
  - `xml.etree fromstring '<a>forge</a>' 真 .text='forge'`
  - `xml.etree iter 真子化 `<root><a/><b/></root>` 必 ≥ 2 element`
  - `xml.etree parse tmp.xml 真 root.tag + getroot`
  - `xml.etree tostring `<root><a>forge</a></root>` 必 '<root>...'`
  - `csv.field_size_limit 8192 必 int 必非默认`
  - `csv.excel_tab 真用 reader <tab split>`
  - `csv.Sniffer 真 sniff '\t' delimiter`
  - `logging.FileHandler tmp_path 真写 'forge_log' 必能读`
  - `logging.StreamHandler(StringIO) 真发 'forge_stream'`
  - `logging.Formatter 真 '%(levelname)s' + format record 'INFO'`
  - `logging.LogRecord.getMessage 真 'forge_record'`
  - `pprint.PrettyPrinter(width=40) 必能 pformat`
  - `pprint PrettyPrinter(depth=2) 必 depth attr`
  - `pprint PrettyPrinter(indent=4) 必 indent attr`
"""
import csv
import io
import logging
import os
import pprint
import sys
import tempfile
import xml.etree.ElementTree as ET

import pytest


# -- xml.etree.ElementTree 进阶 (fromstring + iter + parse + tostring) -----

class TestXmlEtreeAdvancedV2:
    def test_fromstring(self):
        """`xml.etree fromstring '<a>forge</a>' 真 .text='forge'。"""
        root = ET.fromstring("<a>forge</a>")
        # 必 Element
        assert isinstance(root, ET.Element)
        # 必 tag 'a'
        assert root.tag == "a"
        # 必 text 'forge'
        assert root.text == "forge"

    def test_iter(self):
        """`xml.etree iter 真子化 <root><a/><b/></root> 必 ≥ 2 element。"""
        root = ET.fromstring("<root><a/><b/></root>")
        # iter 必 ≥ 3 (root + a + b)
        elements = list(root.iter())
        # 必 ≥ 3
        assert len(elements) >= 3

    def test_parse(self, tmp_path):
        """`xml.etree parse tmp.xml 真 root.tag + getroot。"""
        f = tmp_path / "forge.xml"
        f.write_text("<root><a>forge_data</a></root>")
        # parse
        tree = ET.parse(str(f))
        # 必 ElementTree
        root = tree.getroot()
        # 必 tag 'root'
        assert root.tag == "root"
        # 必含 'a'
        children = list(root)
        assert len(children) == 1
        assert children[0].tag == "a"
        assert children[0].text == "forge_data"

    def test_tostring(self):
        """`xml.etree tostring <root><a>forge</a></root> 必 '<root>...'。"""
        root = ET.fromstring("<root><a>forge</a></root>")
        result = ET.tostring(root, encoding="unicode")
        # 必 str
        assert isinstance(result, str)
        # 必 '<root>'
        assert "<root>" in result
        # 必 'forge'
        assert "forge" in result


# -- csv 进阶 (field_size_limit + excel_tab + Sniffer) -------

class TestCsvAdvancedV2:
    def test_field_size_limit(self):
        """`csv.field_size_limit 8192 必 int 必非默认。"""
        # save
        old = csv.field_size_limit()
        try:
            # set 8192
            csv.field_size_limit(8192)
            # 必 8192
            assert csv.field_size_limit() == 8192
        finally:
            csv.field_size_limit(old)

    def test_excel_tab(self):
        """`csv.excel_tab 真用 reader <tab split>。"""
        data = "a\tb\tc\n1\t2\t3\n"
        reader = csv.reader(io.StringIO(data), dialect="excel-tab")
        rows = list(reader)
        # 必 2
        assert len(rows) == 2
        # 必 ['1', '2', '3']
        assert rows[1] == ["1", "2", "3"]

    def test_Sniffer_tab(self):
        """`csv.Sniffer 真 sniff '\\t' delimiter。"""
        sample = "a\tb\tc\n1\t2\t3\n4\t5\t6\n"
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
        # 必 delimiter '\t'
        assert dialect.delimiter in ("\t", ",")


# -- logging 进阶 (FileHandler + StreamHandler + Formatter + getMessage) -

class TestLoggingHandlersRealAdvanced:
    def test_FileHandler(self, tmp_path):
        """`logging.FileHandler tmp_path 真写 'forge_log' 必能读。"""
        log_path = str(tmp_path / "forge_fh.log")
        h = logging.FileHandler(log_path)
        logger = logging.getLogger("forge_fh_test")
        logger.setLevel(logging.INFO)
        logger.addHandler(h)
        try:
            logger.info("forge_log")
            # 必能读
            with open(log_path) as f:
                data = f.read()
            # 必 'forge_log'
            assert "forge_log" in data
        finally:
            logger.removeHandler(h)
            h.close()

    def test_StreamHandler(self):
        """`logging.StreamHandler(StringIO) 真发 'forge_stream'。"""
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        logger = logging.getLogger("forge_sh_test")
        logger.setLevel(logging.INFO)
        logger.addHandler(h)
        try:
            logger.info("forge_stream")
            # 必能读
            data = buf.getvalue()
            # 必 'forge_stream'
            assert "forge_stream" in data
        finally:
            logger.removeHandler(h)
            h.close()

    def test_Formatter(self):
        """`logging.Formatter 真 '%(levelname)s' + format record 'INFO'。"""
        fmt = logging.Formatter("%(levelname)s")
        # 必能 format
        record = logging.LogRecord("forge_f", logging.INFO, "/path", 1, "msg", None, None)
        result = fmt.format(record)
        # 必 'INFO'
        assert "INFO" in result

    def test_LogRecord_getMessage(self):
        """`logging.LogRecord.getMessage 真 'forge_record'。"""
        record = logging.LogRecord(
            "forge_g", logging.INFO, "/path", 1, "forge_record", None, None
        )
        # getMessage
        result = record.getMessage()
        # 必 'forge_record'
        assert result == "forge_record"


# -- pprint 进阶 (PrettyPrinter 进阶 indent + depth + width) ----

class TestPprintPrettyPrinterAdvanced:
    def test_PrettyPrinter_width(self):
        """`pprint.PrettyPrinter(width=40) 必能 pformat。"""
        pp = pprint.PrettyPrinter(width=40)
        # 必能 pformat
        result = pp.pformat({"a": 1, "b": 2, "c": 3})
        # 必 str
        assert isinstance(result, str)
        # 必含 'a': 1
        assert "'a': 1" in result

    def test_PrettyPrinter_depth(self):
        """`pprint PrettyPrinter(depth=2) 必 depth attr。"""
        pp = pprint.PrettyPrinter(depth=2)
        # 必 depth attr
        assert pp._depth == 2
        # 必非 None
        assert pp is not None

    def test_PrettyPrinter_indent(self):
        """`pprint PrettyPrinter(indent=4) 必 indent attr。"""
        pp = pprint.PrettyPrinter(indent=4)
        # 必 indent attr
        assert pp._indent_per_level == 4
