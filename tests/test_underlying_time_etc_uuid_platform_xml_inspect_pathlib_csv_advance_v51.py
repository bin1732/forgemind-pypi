# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`time` 进阶 + `uuid` 进阶 + `platform` 进阶 + `xml.etree` 进阶 + `inspect` 进阶 + `pathlib` 进阶 + `csv` 进阶 + 真底层测试。

覆盖 time 4 + uuid 3 + platform 3 + xml.etree 6 + inspect 3 + pathlib 5 + csv 1 (共 25 真测试) 模块:
  - `time.gmtime 2026-01-01`
  - `time.localtime tm_year ≥ 2020`
  - `time.asctime weekday`
  - `time.ctime weekday`
  - `uuid.uuid3 v=3`
  - `uuid.uuid5 v=5`
  - `uuid.getnode int ≥ 0`
  - `platform.system 非空`
  - `platform.release 非空`
  - `platform.machine 非空`
  - `xml.etree XPath './/a' ≥ 2`
  - `xml.etree namespace 'ns'`
  - `xml.etree set 'href'='forge'`
  - `xml.etree.text 'forge'`
  - `xml.etree iter ≥ 1 'a'`
  - `xml.etree findall './/b' ≥ 1`
  - `xml.etree clear .text=None`
  - `inspect.signature Signature parameters`
  - `inspect.Signature.bind a=1 b='forge_value'`
  - `inspect.Signature.replace 'forge_replaced'`
  - `pathlib.resolve absolute`
  - `pathlib.iterdir tmp_path ≥ 2`
  - `pathlib.glob '*.txt' ≥ 1`
  - `pathlib.with_name 'new.txt'`
  - `pathlib.with_suffix '.txt'`
  - `csv.field_size_limit ≥ 0`
"""
import csv
import inspect
import pathlib
import platform
import time
import uuid
import xml.etree.ElementTree as ET

import pytest


def _forge_inspect_sig44(a: int, b: str = "forge") -> str:
    return f"{a}{b}"


# -- time 进阶 (gmtime+localtime+asctime+ctime) -------

class TestTimeAdvanceV47:
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

class TestUuidAdvanceV46:
    def test_uuid3(self):
        """`uuid.uuid3 v=3。"""
        u = uuid.uuid3(uuid.NAMESPACE_DNS, "forge.example.com")
        assert len(str(u)) == 36
        assert u.version == 3

    def test_uuid5(self):
        """`uuid.uuid5 v=5。"""
        u = uuid.uuid5(uuid.NAMESPACE_DNS, "forge.example.com")
        assert len(str(u)) == 36
        assert u.version == 5

    def test_getnode(self):
        """`uuid.getnode int ≥ 0。"""
        node = uuid.getnode()
        assert isinstance(node, int)
        assert node >= 0


# -- platform 进阶 (system+release+machine) -----

class TestPlatformAdvanceV46:
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

    def test_machine(self):
        """`platform.machine 非空。"""
        s = platform.machine()
        assert isinstance(s, str)
        assert len(s) > 0


# -- xml.etree 进阶 (XPath+namespace+set+text+iter+findall+clear) ---

class TestXmlEtreeAdvanceV46:
    def test_XPath(self):
        """`xml.etree XPath './/a' ≥ 2。"""
        root = ET.fromstring("<r><a/><a/></r>")
        elements = root.findall(".//a")
        assert len(elements) >= 2

    def test_namespace(self):
        """`xml.etree namespace 'ns'。"""
        ns = "http://forge.example.com/ns"
        root = ET.fromstring(f'<a xmlns="{ns}"><b/></a>')
        assert ns in str(ET.tostring(root, encoding="unicode"))

    def test_set_get_attribute(self):
        """`xml.etree set 'href'='forge'。"""
        a = ET.Element("a")
        a.set("href", "forge")
        assert a.get("href") == "forge"

    def test_text(self):
        """`xml.etree.text 'forge'。"""
        a = ET.Element("a")
        a.text = "forge"
        assert a.text == "forge"

    def test_iter_findall(self):
        """`xml.etree iter ≥ 1 'a' + findall './/b' ≥ 1。"""
        root = ET.fromstring("<r><a><b/></a></r>")
        elements = list(root.iter("a"))
        assert len(elements) >= 1
        # findall
        b_elements = root.findall(".//b")
        assert len(b_elements) >= 1

    def test_clear(self):
        """`xml.etree clear .text=None。"""
        a = ET.fromstring("<a>old</a>")
        a.clear()
        assert a.text is None


# -- inspect 进阶 (signature+bind+replace) ------------

class TestInspectAdvanceV47:
    def test_signature(self):
        """`inspect.signature Signature parameters。"""
        sig = inspect.signature(_forge_inspect_sig44)
        assert isinstance(sig, inspect.Signature)
        assert "a" in sig.parameters

    def test_Signature_bind(self):
        """`inspect.Signature.bind a=1 b='forge_value'。"""
        sig = inspect.signature(_forge_inspect_sig44)
        bound = sig.bind(a=1, b="forge_value")
        assert bound.arguments["a"] == 1

    def test_Signature_replace(self):
        """`inspect.Signature.replace 'forge_replaced'。"""
        sig = inspect.signature(_forge_inspect_sig44)
        new_sig = sig.replace(
            parameters=[
                sig.parameters["a"],
                sig.parameters["b"].replace(default="forge_replaced"),
            ]
        )
        assert new_sig.parameters["b"].default == "forge_replaced"


# -- pathlib 进阶 (resolve+iterdir+glob+with_name+with_suffix) ---

class TestPathlibAdvanceV50:
    def test_resolve(self, tmp_path):
        """`pathlib.resolve absolute。"""
        f = tmp_path / "forge_resolve.txt"
        f.write_text("forge")
        assert f.resolve().is_absolute()

    def test_iterdir(self, tmp_path):
        """`pathlib.iterdir tmp_path ≥ 2。"""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        entries = list(tmp_path.iterdir())
        assert len(entries) >= 2

    def test_glob(self, tmp_path):
        """`pathlib.glob '*.txt' ≥ 1。"""
        (tmp_path / "forge_glob.txt").write_text("forge")
        result = list(tmp_path.glob("*.txt"))
        assert len(result) >= 1

    def test_with_name(self, tmp_path):
        """`pathlib.with_name 'new.txt'。"""
        f = tmp_path / "forge_old.txt"
        f.write_text("forge")
        f2 = f.with_name("new.txt")
        assert f2.name == "new.txt"

    def test_with_suffix(self, tmp_path):
        """`pathlib.with_suffix '.txt'。"""
        f = tmp_path / "forge_old.py"
        f.write_text("forge")
        f2 = f.with_suffix(".txt")
        assert f2.suffix == ".txt"


# -- csv 进阶 (field_size_limit) ---

class TestCsvAdvanceV41:
    def test_field_size_limit(self):
        """`csv.field_size_limit ≥ 0。"""
        old = csv.field_size_limit()
        assert isinstance(old, int)
        assert old >= 0
        csv.field_size_limit(old)
