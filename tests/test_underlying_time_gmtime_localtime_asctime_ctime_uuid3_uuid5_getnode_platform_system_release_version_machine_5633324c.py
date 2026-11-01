# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`time 进阶 (gmtime+localtime+asctime+ctime 真)` + `uuid 进阶 (uuid3+uuid5+getnode 真)` + `platform 进阶 (system+release+version+machine 真)` + `xml.etree 进阶 (XPath+namespace+text+remove+append+findall+clear 真)` + `inspect 进阶 (signature+Parameter+Signature+bind+replace 真)` + 真底层测试。

覆盖 time 4 真 + uuid 3 真 + platform 4 真 + xml.etree 6 真 + inspect 4 真 (共 21 真测试) 模块:
  - `time.gmtime 2026-01-01`
  - `time.localtime tm_year ≥ 2020`
  - `time.asctime weekday`
  - `time.ctime weekday`
  - `uuid.uuid3 v=3`
  - `uuid.uuid5 v=5`
  - `uuid.getnode int ≥ 0`
  - `platform.system 非空`
  - `platform.release 非空`
  - `platform.version 非空`
  - `platform.machine 非空`
  - `xml.etree XPath './/a' ≥ 2`
  - `xml.etree namespace 'ns'`
  - `xml.etree.text 'forge'`
  - `xml.etree remove 必 len 减 1`
  - `xml.etree append 必 len 加 1`
  - `xml.etree findall './/b' ≥ 1`
  - `inspect.signature Signature parameters`
  - `inspect.Parameter.empty sentinel`
  - `inspect.Signature.bind a=1 b='forge_value'`
  - `inspect.Signature.replace 'forge_replaced'`
"""
import inspect
import platform
import time
import uuid
import xml.etree.ElementTree as ET

import pytest


def _forge_inspect_sig4(a: int, b: str = "forge") -> str:
    return f"{a}{b}"


# -- time 进阶 (gmtime+localtime+asctime+ctime) -------

class TestTimeAdvanceV7:
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

class TestUuidAdvanceV6:
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


# -- platform 进阶 (system+release+version+machine) -----

class TestPlatformAdvanceV6:
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


# -- xml.etree 进阶 (XPath+namespace+text+remove+append+findall+clear) ---

class TestXmlEtreeAdvanceV6:
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

    def test_text(self):
        """`xml.etree.text 'forge'。"""
        a = ET.Element("a")
        a.text = "forge"
        assert a.text == "forge"

    def test_remove(self):
        """`xml.etree remove 必 len 减 1。"""
        root = ET.fromstring("<r><a/><a/></r>")
        assert len(list(root.iter("a"))) == 2
        root.remove(list(root.iter("a"))[0])
        assert len(list(root.iter("a"))) == 1

    def test_append(self):
        """`xml.etree append 必 len 加 1。"""
        root = ET.fromstring("<r><a/></r>")
        assert len(list(root.iter("a"))) == 1
        root.append(ET.Element("a"))
        assert len(list(root.iter("a"))) == 2

    def test_findall(self):
        """`xml.etree findall './/b' ≥ 1。"""
        root = ET.fromstring("<r><b>1</b><a><b>2</b></a></r>")
        elements = root.findall(".//b")
        assert len(elements) >= 1


# -- inspect 进阶 (signature+Parameter+Signature+bind+replace) --

class TestInspectAdvanceV7:
    def test_signature(self):
        """`inspect.signature Signature parameters。"""
        sig = inspect.signature(_forge_inspect_sig4)
        assert isinstance(sig, inspect.Signature)
        assert "a" in sig.parameters

    def test_Parameter_empty(self):
        """`inspect.Parameter.empty sentinel。"""
        empty = inspect.Parameter.empty
        assert empty is not None

    def test_Signature_bind(self):
        """`inspect.Signature.bind a=1 b='forge_value'。"""
        sig = inspect.signature(_forge_inspect_sig4)
        bound = sig.bind(a=1, b="forge_value")
        assert bound.arguments["a"] == 1

    def test_Signature_replace(self):
        """`inspect.Signature.replace 'forge_replaced'。"""
        sig = inspect.signature(_forge_inspect_sig4)
        new_sig = sig.replace(
            parameters=[
                sig.parameters["a"],
                sig.parameters["b"].replace(default="forge_replaced"),
            ]
        )
        assert new_sig.parameters["b"].default == "forge_replaced"
