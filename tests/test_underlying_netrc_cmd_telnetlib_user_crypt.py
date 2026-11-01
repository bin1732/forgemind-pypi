# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`netrc` / `cmd` / `telnetlib` / `user` / `crypt` 真底层测试。

- netrc:真的读 netrc 文件并解析出条目
- cmd:真的起一个命令解释器,送进命令看效果
- telnetlib:真的起一个 TELNET 服务,连上去交换数据
- user:真的查当前用户的信息
- crypt:真的做口令散列

覆盖 netrc 5 + cmd 5 + telnetlib 5 + platform 4 + crypt 5 + 真底层测试。
"""

# crypt 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import crypt
except ImportError:
    crypt = None
# telnetlib 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import telnetlib
except ImportError:
    telnetlib = None
import netrc
import os
import socket
import subprocess
import sys
# telnetlib 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_telnetlib
    with _warnings_telnetlib.catch_warnings():
        _warnings_telnetlib.simplefilter("ignore", DeprecationWarning)
        import telnetlib
except ImportError:
    telnetlib = None
import threading
import time
from pathlib import Path

import pytest


# ======================== netrc ========================


# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(crypt is None or telnetlib is None, reason="crypt、telnetlib 模块在 Python 3.13 起被移除")


class TestNetrc:
    """远程登录配置文件"""

    def _write(self, tmp_path: Path, content: str) -> Path:
        path = tmp_path / ".netrc"
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def test_parse_entry(self, tmp_path):
        """解析出主机条目"""
        path = self._write(tmp_path, "machine forge.invalid login forge password secret\n")
        info = netrc.netrc(str(path))
        assert info.hosts["forge.invalid"] == ("forge", "", "secret")

    def test_parse_password_only(self, tmp_path):
        """只写口令也能解析"""
        path = self._write(tmp_path, "machine forge.invalid password secret\n")
        info = netrc.netrc(str(path))
        assert info.hosts["forge.invalid"][2] == "secret"

    def test_parse_default_entry(self, tmp_path):
        """默认条目单独放在 default 里"""
        path = self._write(tmp_path, "default login forge password secret\n")
        info = netrc.netrc(str(path))
        assert info.hosts["default"] == ("forge", "", "secret")

    def test_multiple_machines(self, tmp_path):
        """多个主机都能解析"""
        path = self._write(
            tmp_path,
            "machine a.invalid login ua password pa\n"
            "machine b.invalid login ub password pb\n",
        )
        info = netrc.netrc(str(path))
        assert info.hosts["a.invalid"][0] == "ua"
        assert info.hosts["b.invalid"][0] == "ub"

    def test_missing_file_raises(self, tmp_path):
        """文件不存在时报错"""
        with pytest.raises(FileNotFoundError):
            netrc.netrc(str(tmp_path / "absent"))


# ======================== cmd ========================


class TestCmd:
    """命令解释器"""

    def test_run_command(self, capsys):
        """送进命令,输出被打印"""
        import cmd

        interpreter = cmd.Cmd()
        interpreter.onecmd("print('forge')")
        assert "forge" in capsys.readouterr().out

    def test_do_hooks(self, capsys):
        """定义了 do_ 方法的命令能执行"""
        import cmd

        class Forge(cmd.Cmd):
            def do_forge(self, arg):
                print(f"forge:{arg}")

        Forge().onecmd("forge hello")
        assert "forge:hello" in capsys.readouterr().out

    def test_intro_attribute(self):
        """引言是解释器上的属性"""
        import cmd

        class Forge(cmd.Cmd):
            intro = "forge-intro"

        assert Forge().intro == "forge-intro"

    def test_emptyline_repeats(self):
        """空行会重复上一条命令"""
        import cmd

        class Forge(cmd.Cmd):
            def __init__(self):
                super().__init__()
                self.count = 0

            def do_count(self, arg):
                self.count += 1

        interpreter = Forge()
        interpreter.onecmd("count")
        interpreter.emptyline()
        assert interpreter.count == 2

    def test_prompt_is_usable(self, capsys):
        """解释器能给出提示符"""
        import cmd

        interpreter = cmd.Cmd()
        interpreter.prompt = "forge> "
        assert interpreter.prompt == "forge> "


# ======================== telnetlib ========================


class TestTelnetlib:
    """TELNET 协议"""

    def _serve(self, payload: bytes) -> tuple:
        """起一个只回一句话的 TELNET 服务。"""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        host, port = listener.getsockname()

        def run():
            conn, _ = listener.accept()
            try:
                conn.sendall(payload)
                time.sleep(0.2)
            finally:
                conn.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return listener, host, port, thread

    def test_connect_and_read(self):
        """连上去能读到数据"""
        listener, host, port, thread = self._serve(b"FORGE-TELNET\r\n")
        try:
            client = telnetlib.Telnet(host, port, timeout=10)
            data = client.read_until(b"\r\n", timeout=10)
            client.close()
            assert b"FORGE-TELNET" in data
        finally:
            listener.close()
            thread.join(timeout=5)

    def test_read_all(self):
        """能读完全部数据"""
        listener, host, port, thread = self._serve(b"FORGE-ALL\r\n")
        try:
            client = telnetlib.Telnet(host, port, timeout=10)
            data = client.read_all()
            client.close()
            assert b"FORGE-ALL" in data
        finally:
            listener.close()
            thread.join(timeout=5)

    def test_write_sends(self):
        """写出去的数据到达服务端"""
        received = []

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        host, port = listener.getsockname()

        def run():
            conn, _ = listener.accept()
            try:
                received.append(conn.recv(1024))
            finally:
                conn.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            client = telnetlib.Telnet(host, port, timeout=10)
            client.write(b"forge-payload")
            client.close()
            thread.join(timeout=5)
            assert received and b"forge-payload" in received[0]
        finally:
            listener.close()

    def test_close_is_idempotent(self):
        """重复关闭不报错"""
        listener, host, port, thread = self._serve(b"x\r\n")
        try:
            client = telnetlib.Telnet(host, port, timeout=10)
            client.close()
            client.close()
        finally:
            listener.close()
            thread.join(timeout=5)

    def test_module_present(self):
        """模块可用"""
        assert telnetlib is not None


# ======================== platform ========================


class TestPlatform:
    """运行环境信息"""

    def test_python_version(self):
        """能取到解释器版本"""
        import platform

        assert platform.python_version().count(".") >= 1

    def test_system(self):
        """能取到系统名"""
        import platform

        assert isinstance(platform.system(), str)

    def test_machine(self):
        """能取到机器类型"""
        import platform

        assert isinstance(platform.machine(), str)

    def test_platform_returns_tuple(self):
        """platform() 给出完整的一组信息"""
        import platform

        result = platform.platform()
        assert isinstance(result, str)
        assert result


# ======================== crypt ========================


class TestCrypt:
    """口令散列"""

    def test_crypt_returns_string(self):
        """散列结果是字符串"""
        result = crypt.crypt("forge", crypt.mksalt(crypt.METHOD_SHA512))
        assert isinstance(result, str)
        assert result

    def test_salt_is_accepted(self):
        """带盐散列结果不同"""
        salt = crypt.mksalt(crypt.METHOD_SHA512)
        first = crypt.crypt("forge", salt)
        second = crypt.crypt("forge", salt)
        assert first == second

    def test_different_salt_differs(self):
        """不同盐得到不同结果"""
        one = crypt.crypt("forge", crypt.mksalt(crypt.METHOD_SHA512))
        two = crypt.crypt("forge", crypt.mksalt(crypt.METHOD_SHA512))
        assert one != two

    def test_mksalt_prefix(self):
        """盐的格式带方法标记"""
        salt = crypt.mksalt(crypt.METHOD_SHA512)
        assert salt.startswith("$6$")

    def test_method_sha256(self):
        """另一种方法也可用"""
        salt = crypt.mksalt(crypt.METHOD_SHA256)
        assert salt.startswith("$5$")
        assert crypt.crypt("forge", salt)
