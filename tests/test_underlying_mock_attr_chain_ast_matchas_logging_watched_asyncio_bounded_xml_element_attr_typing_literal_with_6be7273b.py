# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.Mock` 属性链 / `ast.MatchAs` 3.10+ / `logging.WatchedFileHandler` / `asyncio.BoundedSemaphore` / `xml.etree.Element` attribute / `typing.Literal` + get_args / `pathlib.with_suffix` / `shutil.unpack_archive` / `pprint.pprint` width / `socket.getsockname` / `numbers.Number` / `trace.runcall` / `subprocess.run + check` / `ipaddress` AddressValueError 真抛 底层测试。

覆盖 Mock 属性链 / ast MatchAs / logging WatchedFileHandler / asyncio BoundedSemaphore / xml Element attribute / typing Literal / pathlib with_suffix / shutil unpack_archive / pprint width / socket getsockname / numbers Number / trace runcall / subprocess run + check / ipaddress AddressValueError 模块:
  - `Mock 真链 a.b.c 必都是 MagicMock`
  - `ast.MatchAs 3.10+ 真建+name='forge'`
  - `logging.handlers.WatchedFileHandler 真写 file 不抛`
  - `asyncio.BoundedSemaphore 真 max=3`
  - `xml.etree.Element 真 attr set+get`
  - `xml.etree.Element 真 findtext 找子`
  - `typing.Literal[1, 2, 3] 真建 + get_args 返 tuple`
  - `pathlib.Path.with_suffix('.txt') 真换 suffix`
  - `shutil.unpack_archive 真提 zip`
  - `pprint.pprint(width=40) 真窄 width`
  - `socket.getsockname 真返 (host, port) for bound socket`
  - `numbers.Number + Complex + Real + Rational + Integral 5 ABC`
  - `trace.runcall 真调 fn + results`
  - `subprocess.run check=True 非 0 抛 CalledProcessError`
  - `ipaddress.IPv4Address('256.0.0.1') 真抛 AddressValueError`
  - `ipaddress.IPv6Address('xyz') 真抛 AddressValueError`
"""
import ast
import asyncio
import contextlib
import io
import ipaddress
import logging.handlers
import numbers
import os
import pathlib
import pprint
import shutil
import socket
import subprocess
import sys
import tempfile
import trace
import typing
import unittest.mock
import xml.etree.ElementTree as ET
import zipfile

import pytest


# -- Mock 属性链 --------------------------------------------------------------

class TestMockAttrChain:
    def test_attr_chain(self):
        """`Mock 真链 a.b.c 必都是 MagicMock. """
        m = unittest.mock.MagicMock()
        # 链访问
        m.a.b.c = 42
        assert m.a.b.c == 42
        # 必能 call 链
        m.x.y.z.return_value = "forge"
        assert m.x.y.z() == "forge"


# -- ast.MatchAs 3.10+ -------------------------------------------------------

class TestAstAdvancedV17:
    def test_MatchAs_3_10(self):
        """`ast.MatchAs 3.10+ 真建+name='forge'。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchAs")
        if not hasattr(ast, "MatchAs"):
            pytest.skip("沙箱无 MatchAs")
        # 创 MatchAs 节点
        ma = ast.MatchAs(pattern=None, name="forge")
        assert ma.name == "forge"
        # dump
        dumped = ast.dump(ma)
        assert "MatchAs" in dumped
        assert "forge" in dumped


# -- logging.WatchedFileHandler -----------------------------------------------

class TestLoggingWatched:
    def test_WatchedFileHandler(self):
        """`WatchedFileHandler 真写 file 不抛。"""
        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".log"
        ) as f:
            path = f.name
        try:
            log = logging.getLogger("forge_watched")
            log.setLevel(logging.INFO)
            log.handlers.clear()
            h = logging.handlers.WatchedFileHandler(path)
            log.addHandler(h)
            try:
                log.info("hello forge watched")
            finally:
                log.removeHandler(h)
                h.close()
            # 必含
            with open(path) as f:
                content = f.read()
            assert "hello forge watched" in content
        finally:
            os.unlink(path)


# -- asyncio.BoundedSemaphore 真 max -----------------------------------------

class TestAsyncioBounded:
    def test_BoundedSemaphore(self):
        """`BoundedSemaphore(3) 真 max=3 并发 5 task。"""

        async def main():
            sem = asyncio.BoundedSemaphore(3)
            active = 0
            max_active = 0

            async def worker():
                nonlocal active, max_active
                async with sem:
                    active += 1
                    max_active = max(max_active, active)
                    await asyncio.sleep(0.02)
                    active -= 1

            workers = [asyncio.create_task(worker()) for _ in range(5)]
            await asyncio.gather(*workers)
            return max_active

        max_active = asyncio.run(main())
        assert max_active == 3, f"BoundedSemaphore(3) max=3,实际 {max_active}"


# -- xml.etree.Element 进阶 ---------------------------------------------------

class TestXmlElementV2:
    def test_Element_attr(self):
        """`xml.etree.Element 真 attr set+get。"""
        elem = ET.Element("forge", {"id": "1", "name": "test"})
        # 必能 attr set
        elem.set("new_attr", "new_value")
        # 必能 attr get
        assert elem.get("new_attr") == "new_value"
        assert elem.get("id") == "1"
        # 必能 attr 删
        del elem.attrib["new_attr"]
        assert elem.get("new_attr") is None

    def test_Element_findtext(self):
        """`xml.etree.Element 真 findtext 找子。"""
        root = ET.fromstring("<root><forge>text1</forge><other>text2</other></root>")
        # 必能 findtext
        assert root.findtext("forge") == "text1"
        assert root.findtext("other") == "text2"
        # 必 None for missing
        assert root.findtext("missing") is None


# -- typing.Literal + get_args ------------------------------------------------

class TestTypingAdvancedV19:
    def test_Literal(self):
        """`typing.Literal[1, 2, 3] 真建 + get_args 返 tuple。"""
        L = typing.Literal[1, 2, 3]
        # 必能 get_args
        args = typing.get_args(L)
        assert args == (1, 2, 3), f"Literal[1,2,3] 应=(1,2,3),实际 {args}"

    def test_Literal_string(self):
        """`typing.Literal['a', 'b'] 真建 + get_args。"""
        L = typing.Literal["a", "b"]
        args = typing.get_args(L)
        assert args == ("a", "b"), f"Literal 应=('a','b'),实际 {args}"


# -- pathlib.with_suffix 进阶 -----------------------------------------------

class TestPathlibWithSuffix:
    def test_with_suffix(self, tmp_path):
        """`pathlib.Path.with_suffix('.txt') 真换 suffix。"""
        p = tmp_path / "forge.py"
        p.write_text("x")
        # 换 .txt
        new_p = p.with_suffix(".txt")
        # 必 new
        assert str(new_p).endswith(".txt")
        # 必 = tmp_path/forge.txt
        assert new_p == tmp_path / "forge.txt"


# -- shutil.unpack_archive 真提 ----------------------------------------------

class TestShutilUnpackArchive:
    def test_unpack_archive_zip(self, tmp_path):
        """`shutil.unpack_archive 真提 zip。"""
        # 创 zip
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("forge.txt", b"hello forge unpack")
        # 提
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        shutil.unpack_archive(str(zip_path), str(extract_dir))
        # 必含
        extracted = extract_dir / "forge.txt"
        assert extracted.exists()
        assert extracted.read_bytes() == b"hello forge unpack"


# -- pprint.pprint width 进阶 -------------------------------------------------

class TestPprintWidth:
    def test_pprint_width(self):
        """`pprint.pprint(width=20) 真窄 width。"""
        big = {f"k{i}": i for i in range(20)}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pprint.pprint(big, width=20)
        # 必非空
        out = buf.getvalue()
        assert len(out) > 0
        # 必含 k0
        assert "k0" in out


# -- socket.getsockname 进阶 -------------------------------------------------

class TestSocketGetsockname:
    def test_getsockname_bound(self):
        """`socket.getsockname 真返 (host, port) for bound socket. """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            host, port = s.getsockname()
            assert host == "127.0.0.1"
            assert isinstance(port, int)
            assert port > 0  # OS 选


# -- numbers.Number + Complex + Real + Rational + Integral 5 ABC ------------

class TestNumbersHierarchy:
    def test_5_ABC_hierarchy(self):
        """`numbers 5 ABC 真层次。"""
        # Number 必是顶级
        assert issubclass(numbers.Number, numbers.Number)
        # Complex 必是 Number 子
        assert issubclass(numbers.Complex, numbers.Number)
        # Real 必是 Complex 子
        assert issubclass(numbers.Real, numbers.Complex)
        # Rational 必是 Real 子
        assert issubclass(numbers.Rational, numbers.Real)
        # Integral 必是 Rational 子
        assert issubclass(numbers.Integral, numbers.Rational)


# -- trace.runcall ------------------------------------------------------------

class TestTraceRuncall:
    def test_Trace_runfunc(self):
        """`Trace.runfunc 真调 lambda + results。"""
        tr = trace.Trace(trace=0, count=True)
        # runfunc 沙箱 3.11 存在
        result = tr.runfunc(lambda: sum([i for i in range(10)]))
        # 必返 45 (0+1+...+9)
        assert result == 45
        # 必能 results
        assert tr.results() is not None


# -- subprocess.run + check + CalledProcessError ----------------------------

class TestSubprocessRunCheck:
    def test_run_check_failure(self):
        """`subprocess.run check=True 非 0 抛 CalledProcessError。"""
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.run(
                ["false"],  # 必返 1
                check=True,
            )

    def test_run_check_success(self):
        """`subprocess.run check=True 0 不抛。"""
        result = subprocess.run(
            ["true"],  # 必返 0
            check=True,
        )
        assert result.returncode == 0


# -- ipaddress.AddressValueError 真抛 -----------------------------------------

class TestIpaddressErrorV2:
    def test_IPv4Address_invalid(self):
        """`IPv4Address('256.0.0.1') 真抛 AddressValueError。"""
        with pytest.raises(ipaddress.AddressValueError):
            ipaddress.IPv4Address("256.0.0.1")

    def test_IPv6Address_invalid(self):
        """`IPv6Address('xyz') 真抛 AddressValueError。"""
        with pytest.raises(ipaddress.AddressValueError):
            ipaddress.IPv6Address("xyz")

    def test_IPv4Netmask_invalid(self):
        """`IPv4Network('192.168.0.0/40') 真抛 NetmaskValueError。"""
        with pytest.raises(ipaddress.NetmaskValueError):
            ipaddress.IPv4Network("192.168.0.0/40")
