# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree.XPath` 进阶 (findall+text+find+iter+namespace 真) + `csv.Sniffer/excel/excel_tab/DictWriter/DictReader 真` + `pathlib 进阶 (with_suffix+with_name+stem+suffix+parent+iterdir+walk+glob 真)` + 真底层测试。

覆盖 xml.etree 3 真 (XPath+text+iter 真) + csv 2 真 (Sniffer+excel_tab 真) + pathlib 6 真 (with_suffix+with_name+stem+suffix+parent+iterdir) (共 11 真测试) 模块:
  - `xml.etree.findall './/a' 真 2 fromstring '<r><a/><a/></r>'`
  - `xml.etree 真 text='forge' fromstring '<a>forge</a>'`
  - `xml.etree 真 iter+tag 真 ≥ 1 element`
  - `csv.Sniffer sniff 真 ',' delimiter 'a,b,c\\n1,2,3'`
  - `csv 真 excel_tab reader 必含 '1' '2' '3'`
  - `pathlib with_suffix('.txt') 真 .suffix='.txt'`
  - `pathlib with_name('new.txt') 真 .name='new.txt'`
  - `pathlib Path 'forge.py' stem 必 'forge'`
  - `pathlib Path 'forge.py' suffix 必 '.py'`
  - `pathlib Path '/a/b/c' parent 必 '/a/b'`
  - `pathlib iterdir tmp_path 必 ≥ 1 DirEntry`
"""
import csv
import io
import pathlib
import xml.etree.ElementTree as ET

import pytest


# -- xml.etree 进阶 (findall + text + iter) ---------------

class TestXmlEtreeAdvancedV3:
    def test_findall_xpath(self):
        """`xml.etree.findall './/a' 真 2 fromstring '<r><a/><a/></r>'。"""
        root = ET.fromstring("<r><a/><a/></r>")
        # findall './/a'
        elements = root.findall(".//a")
        # 必 2
        assert len(elements) == 2

    def test_text_get(self):
        """`xml.etree 真 text='forge' fromstring '<a>forge</a>'。"""
        a = ET.fromstring("<a>forge</a>")
        # 必 'forge'
        assert a.text == "forge"

    def test_iter_tag(self):
        """`xml.etree 真 iter+tag 真 ≥ 1 element。"""
        root = ET.fromstring("<r><a/><b/></r>")
        # iter 'a' 必 ≥ 1
        elements = list(root.iter("a"))
        # 必 ≥ 1
        assert len(elements) >= 1


# -- csv 进阶 (Sniffer + excel_tab) -----------------------

class TestCsvAdvancedV4:
    def test_Sniffer_comma(self):
        """`csv.Sniffer sniff 真 ',' delimiter 'a,b,c\\n1,2,3'。"""
        sample = "a,b,c\n1,2,3\n4,5,6\n"
        dialect = csv.Sniffer().sniff(sample, delimiters=",")
        # 必 delimiter ','
        assert dialect.delimiter == ","

    def test_excel_tab_reader(self):
        """`csv 真 excel_tab reader 必含 '1' '2' '3'。"""
        data = "a\tb\tc\n1\t2\t3\n"
        reader = csv.reader(io.StringIO(data), dialect="excel-tab")
        rows = list(reader)
        # 必 2 (含 header)
        assert len(rows) == 2
        # 必含 '1' '2' '3' (data row)
        assert "1" in rows[1]
        assert "2" in rows[1]
        assert "3" in rows[1]


# -- pathlib 进阶 (with_suffix + with_name + stem + suffix + parent + iterdir) -

class TestPathlibAdvancedV7:
    def test_with_suffix(self):
        """`pathlib with_suffix('.txt') 真 .suffix='.txt'。"""
        p = pathlib.Path("/a/b/forge.py")
        # with_suffix
        p2 = p.with_suffix(".txt")
        # 必 .txt
        assert p2.suffix == ".txt"

    def test_with_name(self):
        """`pathlib with_name('new.txt') 真 .name='new.txt'。"""
        p = pathlib.Path("/a/b/forge.py")
        # with_name
        p2 = p.with_name("new.txt")
        # 必 'new.txt'
        assert p2.name == "new.txt"

    def test_stem(self):
        """`pathlib Path 'forge.py' stem 必 'forge'。"""
        p = pathlib.Path("forge.py")
        # 必 'forge'
        assert p.stem == "forge"

    def test_suffix(self):
        """`pathlib Path 'forge.py' suffix 必 '.py'。"""
        p = pathlib.Path("forge.py")
        # 必 '.py'
        assert p.suffix == ".py"

    def test_parent(self):
        """`pathlib Path '/a/b/c' parent 必 '/a/b'。"""
        p = pathlib.PurePath("/a/b/c")
        # 必 '/a/b'
        assert str(p.parent) == "/a/b"

    def test_iterdir(self, tmp_path):
        """`pathlib iterdir tmp_path 必 ≥ 1 DirEntry。"""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        # iterdir
        entries = list((tmp_path).iterdir())
        # 必 ≥ 2
        assert len(entries) >= 2
        # 必含 'a.txt' + 'b.txt'
        names = [e.name for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names
