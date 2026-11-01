# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`time 进阶 (gmtime+localtime+asctime+ctime)` + `uuid 进阶 (uuid3+uuid5+getnode)` + `platform 进阶 (system+release+machine)` + `xml.etree 进阶 (XPath+namespace+set+text+append+remove+findall)` + `inspect 进阶 (signature+bind+replace)` + `pathlib 进阶 (resolve+iterdir+glob+rglob+with_name+with_suffix)` + `csv 进阶 (register_dialect 'forge_d7')` + 真底层测试。

覆盖 time 4 + uuid 3 + platform 3 + xml.etree 6 + inspect 3 + pathlib 6 + csv 1 (共 26 真测试) 模块:
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
  - `xml.etree append 父级 child 增加`
  - `xml.etree remove child`
  - `xml.etree findall './/b' ≥ 1`
  - `inspect.signature Signature parameters`
  - `inspect.Signature.bind a=1 b='forge_value'`
  - `inspect.Signature.replace 'forge_replaced'`
  - `pathlib.resolve absolute`
  - `pathlib.iterdir tmp_path ≥ 2`
  - `pathlib.glob '*.txt' ≥ 1`
  - `pathlib.rglob '*.txt' ≥ 1`
  - `pathlib.with_name 'new.txt'`
  - `pathlib.with_suffix '.txt'`
  - `csv.register_dialect 'forge_d7' 真用`
"""
import csv
import inspect
import pathlib
import platform
import time
import uuid
import xml.etree.ElementTree as ET

import pytest


def _forge_inspect_sig17(a: int, b: str = "forge") -> str:
    return f"{a}{b}"


# -- time 进阶 (gmtime+localtime+asctime+ctime) -------

class TestTimeAdvanceV20:
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

class TestUuidAdvanceV19:
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

class TestPlatformAdvanceV19:
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


# -- xml.etree 进阶 (XPath+namespace+set+text+append+remove+findall) ---

class TestXmlEtreeAdvanceV19:
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

    def test_append_remove(self):
        """`xml.etree append 父级 child 增加 + remove child。"""
        root = ET.fromstring("<r></r>")
        b = ET.Element("b")
        b.text = "forge"
        root.append(b)
        elements = root.findall(".//b")
        assert len(elements) >= 1
        # remove
        root.remove(b)
        assert len(root.findall(".//b")) == 0

    def test_findall(self):
        """`xml.etree findall './/b' ≥ 1。"""
        root = ET.fromstring("<r><b>1</b><a><b>2</b></a></r>")
        elements = root.findall(".//b")
        assert len(elements) >= 1


# -- inspect 进阶 (signature+bind+replace) ------------

class TestInspectAdvanceV20:
    def test_signature(self):
        """`inspect.signature Signature parameters。"""
        sig = inspect.signature(_forge_inspect_sig17)
        assert isinstance(sig, inspect.Signature)
        assert "a" in sig.parameters

    def test_Signature_bind(self):
        """`inspect.Signature.bind a=1 b='forge_value'。"""
        sig = inspect.signature(_forge_inspect_sig17)
        bound = sig.bind(a=1, b="forge_value")
        assert bound.arguments["a"] == 1

    def test_Signature_replace(self):
        """`inspect.Signature.replace 'forge_replaced'。"""
        sig = inspect.signature(_forge_inspect_sig17)
        new_sig = sig.replace(
            parameters=[
                sig.parameters["a"],
                sig.parameters["b"].replace(default="forge_replaced"),
            ]
        )
        assert new_sig.parameters["b"].default == "forge_replaced"


# -- pathlib 进阶 (resolve+iterdir+glob+rglob+with_name+with_suffix) ---

class TestPathlibAdvanceV23:
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

    def test_rglob(self, tmp_path):
        """`pathlib.rglob '*.txt' ≥ 1。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "forge_rglob.txt").write_text("forge")
        result = list(tmp_path.rglob("*.txt"))
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


# -- csv 进阶 (register_dialect 'forge_d7') ---

class TestCsvRegisterDialectV5:
    def test_register_dialect(self):
        """`csv.register_dialect 'forge_d7' 真用。"""
        try:
            csv.register_dialect(
                "forge_d7",
                delimiter="|",
                quotechar="*",
            )
            assert "forge_d7" in csv.list_dialects()
        finally:
            csv.unregister_dialect("forge_d7")
