# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree.Element` 进阶 (find+findall+iter+namespace+clear+set+text+attrib) + `csv.DictReader/DictWriter` 真用 + `csv.field_size_limit` 进阶 + `os.scandir 进阶 (DirEntry+is_file+is_dir+stat)` + 真底层测试。

覆盖 xml.etree 5 真 (find+findall+iter+clear+set+text+attrib) + csv 3 真 (DictReader 真+DictWriter 真+field_size_limit 8192) + os.scandir 2 真 (DirEntry+is_file+is_dir+stat) (共 10 真测试) 模块:
  - `xml.etree.find 'a' fromstring '<root><a>forge</a></root>' 必 .text='forge'`
  - `xml.etree.findall 'a' fromstring '<root><a/><a/></root>' 必 2`
  - `xml.etree.iter 'a' fromstring 必 ≥ 2 element`
  - `xml.etree.Element clear+set 'forge' 必 .text='forge'`
  - `xml.etree.Element attrib 真 dict set 'href'='forge'`
  - `csv.DictReader 真读 'name\\nforge' 必 [{'name': 'forge'}]`
  - `csv.DictWriter 真写 + writeheader + writerow 必 'forge,42'`
  - `csv.field_size_limit 8192 必 8192`
  - `os.scandir tmp_path 必 ≥ 1 DirEntry`
  - `os.DirEntry is_file+is_dir+stat 真用 (is_file=True)`
"""
import csv
import io
import os
import xml.etree.ElementTree as ET

import pytest


# -- xml.etree.Element 进阶 (find + findall + iter + clear + set + text + attrib) ----

class TestXmlEtreeElementAdvanced:
    def test_find(self):
        """`xml.etree.find 'a' fromstring '<root><a>forge</a></root>' 必 .text='forge'。"""
        root = ET.fromstring("<root><a>forge</a></root>")
        a = root.find("a")
        # 必非 None
        assert a is not None
        # 必 'forge'
        assert a.text == "forge"

    def test_findall(self):
        """`xml.etree.findall 'a' fromstring '<root><a/><a/></root>' 必 2。"""
        root = ET.fromstring("<root><a/><a/></root>")
        elements = root.findall("a")
        # 必 2
        assert len(elements) == 2

    def test_iter(self):
        """`xml.etree.iter 'a' fromstring '<root><a/><b/></root>' 必 ≥ 1 element。"""
        root = ET.fromstring("<root><a/><b/></root>")
        # iter 'a' 必 ≥ 1
        elements = list(root.iter("a"))
        # 必 ≥ 1
        assert len(elements) >= 1

    def test_clear_set_text(self):
        """`xml.etree.Element clear+set 'forge' 必 .text='forge'。"""
        a = ET.Element("a")
        # clear (无 op)
        a.clear()
        # set text
        a.text = "forge"
        # 必 'forge'
        assert a.text == "forge"

    def test_attrib_set(self):
        """`xml.etree.Element attrib 真 dict set 'href'='forge'。"""
        a = ET.Element("a")
        # set attrib
        a.set("href", "forge")
        # 必 'forge'
        assert a.get("href") == "forge"


# -- csv 进阶 (DictReader + DictWriter + field_size_limit) ------

class TestCsvAdvancedV3:
    def test_DictReader(self):
        """`csv.DictReader 真读 'name\\nforge' 必 [{'name': 'forge'}]。"""
        data = "name\nforge\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        # 必 1
        assert len(rows) == 1
        # 必 [{'name': 'forge'}]
        assert rows[0]["name"] == "forge"

    def test_DictWriter(self):
        """`csv.DictWriter 真写 + writeheader + writerow 必 'forge,42'。"""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["name", "value"])
        writer.writeheader()
        writer.writerow({"name": "forge", "value": "42"})
        result = buf.getvalue()
        # 必 'name,value' (header)
        assert "name,value" in result
        # 必 'forge,42'
        assert "forge,42" in result

    def test_field_size_limit(self):
        """`csv.field_size_limit 8192 必 8192。"""
        # save
        old = csv.field_size_limit()
        try:
            csv.field_size_limit(8192)
            assert csv.field_size_limit() == 8192
        finally:
            csv.field_size_limit(old)


# -- os.scandir 进阶 (DirEntry + is_file + is_dir + stat) ----

class TestOsScandirAdvancedV2:
    def test_scandir_DirEntry(self, tmp_path):
        """`os.scandir tmp_path 必 ≥ 1 DirEntry。"""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b").mkdir()
        with os.scandir(str(tmp_path)) as it:
            entries = list(it)
        # 必 ≥ 2
        assert len(entries) >= 2
        # 必 DirEntry
        assert all(isinstance(e, os.DirEntry) for e in entries)
        # 必含 'a.txt' + 'b'
        names = [e.name for e in entries]
        assert "a.txt" in names
        assert "b" in names

    def test_DirEntry_is_file_is_dir_stat(self, tmp_path):
        """`os.DirEntry is_file+is_dir+stat 真用 (is_file=True)。"""
        f = tmp_path / "a.txt"
        f.write_text("forge_data")
        with os.scandir(str(tmp_path)) as it:
            entries = list(it)
        # 取 'a.txt'
        a = [e for e in entries if e.name == "a.txt"][0]
        # is_file
        assert a.is_file() is True
        # is_dir
        assert a.is_dir() is False
        # stat
        s = a.stat()
        # 必 st_size
        assert s.st_size == len("forge_data")
