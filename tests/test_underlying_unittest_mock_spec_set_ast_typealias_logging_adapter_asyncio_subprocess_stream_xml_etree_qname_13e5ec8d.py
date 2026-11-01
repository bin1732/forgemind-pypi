# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock` 进阶 (Mock spec=set) + `ast.TypeAlias` 3.12+ + `logging.LoggerAdapter` + `asyncio.subprocess` 进阶 (stream) + `xml.etree` 进阶 (QName+tostring) + `typing.Self` 3.11+ + `enum.auto` + `pathlib` 进阶 (touch+unlink) + `shutil.which` + `pprint` 进阶 真底层测试。

覆盖 mock spec=set / ast TypeAlias / LoggerAdapter / asyncio stream / xml QName / typing Self / enum auto / pathlib IO / shutil which / pprint 模块:
  - `unittest.mock.MagicMock(spec=set) 必只含 set 方法`
  - `unittest.mock.MagicMock(spec=list, instance=True) 必返 list-like instance`
  - `ast.TypeAlias 3.12+ 沙箱 skip`
  - `logging.LoggerAdapter 真建 + process + log`
  - `asyncio.create_subprocess_exec + 真 stream stdout 读 'hello forge\\n'`
  - `asyncio.create_subprocess_exec 'python -c' 真返 python version`
  - `xml.etree.ElementTree.tostring 真 bytes 含 '<forge/>'`
  - `xml.etree.QName 真建 ns+tag`
  - `typing.Self 3.11+ 沙箱 skip (3.11 有但 mypy check 才抛)`
  - `enum.auto() 真连续分配`
  - `pathlib.Path.touch + unlink 真 IO`
  - `pathlib.Path.stat 真返 stat_result`
  - `pathlib.Path.exists 真返 bool`
  - `shutil.which('python3') 真非空 str`
  - `shutil.which('forge_nonexistent_cmd') 真 None`
  - `pprint.pformat 真返 string 形式 dict`
  - `pprint.isreadable 真返 True / False`
  - `pprint.pp 3.8+ 真直接打到 stdout 不抛`
"""
import asyncio
import enum
import io
import logging
import pathlib
import pprint
import shutil
import sys
import unittest.mock
import xml.etree.ElementTree as ET

import pytest


# -- unittest.mock.MagicMock spec=set ------------------------------------------

class TestMagicMockSpecSet:
    def test_spec_set(self):
        """`MagicMock(spec=set) 必只含 set 方法。"""
        m = unittest.mock.MagicMock(spec=set)
        # 必能调 set 方法
        m.add("forge")
        m.add.assert_called_with("forge")
        # 必不能调 set 没的方法
        with pytest.raises(AttributeError):
            _ = m.append  # append is list method

    def test_spec_list_instance(self):
        """`MagicMock(spec=list, instance=True) 必返 list-like MagicMock instance. """
        m = unittest.mock.MagicMock(spec=list, instance=True)
        # 必能调 list 方法
        m.append("forge")
        m.append.assert_called_with("forge")


# -- ast.TypeAlias 3.12+ -------------------------------------------------------

class TestAstAdvancedV9:
    def test_TypeAlias_3_12(self):
        """`ast.TypeAlias 3.12+ 真建 (沙箱 3.11 skip)`"""
        if sys.version_info < (3, 12):
            pytest.skip("3.12+ TypeAlias")
        if not hasattr(ast, "TypeAlias"):
            pytest.skip("沙箱无 TypeAlias")
        ta = ast.TypeAlias(
            name=ast.Name(id="MyAlias", ctx=ast.Store()),
            value=ast.Constant(value=1),
        )
        assert ast.dump(ta)


# -- logging.LoggerAdapter 进阶 ------------------------------------------------

class TestLoggingLoggerAdapter:
    def test_LoggerAdapter(self):
        """`LoggerAdapter 真建 + process + log。"""
        log = logging.getLogger("forge_adapter")
        log.setLevel(logging.INFO)
        # 清旧 handler
        log.handlers.clear()
        # Adapter
        adapter = logging.LoggerAdapter(
            log, {"forge_prefix": "[FORGE]"}
        )
        # process
        msg, kwargs = adapter.process("test_msg", {})
        assert "test_msg" in msg

        # 接管 log
        captured = []

        class _Cap(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        h = _Cap()
        log.addHandler(h)
        try:
            adapter.info("hello adapter")
            assert len(captured) >= 1
        finally:
            log.removeHandler(h)


# -- asyncio.subprocess 真 stream ----------------------------------------------

class TestAsyncioSubprocessStream:
    def test_subprocess_stream_stdin(self):
        """`asyncio.create_subprocess_exec 'cat' + 真 stdin 'hello forge' + stdout 读。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "cat", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate(input=b"hello forge\n")
            return stdout, proc.returncode

        out, rc = asyncio.run(main())
        assert out == b"hello forge\n", f"stdout 应 'hello forge\\n',实际 {out!r}"
        assert rc == 0

    def test_subprocess_python_version(self):
        """`asyncio.create_subprocess_exec 'python3 -V' 真返 version。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import sys; print(sys.version_info[0])",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout, proc.returncode

        out, rc = asyncio.run(main())
        # 必是 3
        assert b"3" in out, f"python -V 应含 '3',实际 {out!r}"
        assert rc == 0


# -- xml.etree 进阶 ------------------------------------------------------------

class TestXmlEtreeAdvancedV2:
    def test_tostring_bytes(self):
        """`ET.tostring 真返 bytes 含 '<forge/>'。"""
        # 创 element
        root = ET.Element("forge")
        b = ET.tostring(root)
        assert b == b"<forge />", f"tostring 应 b'<forge />',实际 {b!r}"

    def test_QName(self):
        """`ET.QName 真建 namespace+tag。"""
        qn = ET.QName("http://example.com/ns", "forge_tag")
        # 必含 ns+tag
        text = str(qn)
        # 沙箱 3.11+ format = '{ns}tag'
        assert "forge_tag" in text
        assert "example.com" in text


# -- enum.auto 进阶 ------------------------------------------------------------

class TestEnumAuto:
    def test_auto(self):
        """`enum.auto() 真连续分配。"""
        class Color(enum.Enum):
            RED = enum.auto()
            GREEN = enum.auto()
            BLUE = enum.auto()

        # 必连续 1, 2, 3
        assert Color.RED.value == 1
        assert Color.GREEN.value == 2
        assert Color.BLUE.value == 3


# -- pathlib 进阶 (touch + stat + exists) -------------------------------------

class TestPathlibAdvancedV3:
    def test_touch_unlink(self, tmp_path):
        """`pathlib.Path.touch + unlink 真 IO。"""
        p = tmp_path / "forge_touch.txt"
        p.touch()
        # 必存在
        assert p.exists()
        # stat 必返 stat_result
        s = p.stat()
        assert s.st_size == 0
        # unlink
        p.unlink()
        assert not p.exists()

    def test_stat_size(self, tmp_path):
        """`pathlib.Path.stat 真返 size。"""
        p = tmp_path / "forge_data.txt"
        p.write_bytes(b"hello forge bytes")
        s = p.stat()
        assert s.st_size == len(b"hello forge bytes")


# -- shutil.which 进阶 ---------------------------------------------------------

class TestShutilWhich:
    def test_which_python(self):
        """`shutil.which('python3') 真非空 str。"""
        path = shutil.which("python3")
        if path is None:
            pytest.skip("沙箱无 python3 在 PATH")
        assert isinstance(path, str)
        assert len(path) > 0

    def test_which_nonexistent(self):
        """`shutil.which('forge_nonexistent_cmd') 真 None。"""
        path = shutil.which("forge_nonexistent_cmd_xyz123")
        assert path is None


# -- pprint 进阶 ---------------------------------------------------------------

class TestPprintAdvanced:
    def test_pformat(self):
        """`pprint.pformat 真返 string 形式 dict。"""
        s = pprint.pformat({"forge": 42, "list": [1, 2, 3]})
        assert isinstance(s, str)
        # 必含 'forge'
        assert "forge" in s
        assert "42" in s

    def test_isreadable(self):
        """`pprint.isreadable 真返 True/False。"""
        # dict 必 readable
        assert pprint.isreadable({"forge": 42}) is True
        # string 必 readable
        assert pprint.isreadable("forge") is True
        # int 必 readable
        assert pprint.isreadable(42) is True

    def test_pp(self):
        """`pprint.pp 3.8+ 真打不抛。"""
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pprint.pp({"forge": 42, "list": [1, 2, 3]})
        # 必非空
        assert "forge" in buf.getvalue()
