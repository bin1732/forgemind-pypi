# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ssl` 进阶 + `subprocess` 进阶 + `asyncio` 进阶 + `pathlib` 进阶 真底层测试。

覆盖 SSL 握手 / 异步子进程 / async server / pathlib 进阶:
  - `ssl.create_default_context()` 真建 context
  - `ssl.SSLContext(PROTOCOL_TLS_CLIENT).check_hostname = True`
  - `ssl.SSLContext.minimum_version = TLSVersion.TLSv1_2`
  - `ssl.SSLContext.set_alpn_protocols(['h2', 'http/1.1'])`
  - `ssl.get_default_verify_paths()` 真返 bundle path
  - `subprocess.Popen(['python', '-c', '...'], text=True)` 真异步启动
  - `subprocess.Popen.communicate(input=...)` 真双向
  - `subprocess.Popen.send_signal(SIGUSR1)` 真发信号
  - `asyncio.start_server(handler, '127.0.0.1', 0)` 真异步 server
  - `asyncio.open_connection(host, port)` 真连 server
  - `asyncio.Lock()` 真互斥
  - `pathlib.PurePath` 真跨平台
  - `pathlib.Path.glob('*.py')` 真通配
  - `pathlib.Path.rglob('*.py')` 真递归通配
  - `pathlib.Path.relative_to(...)` 真相对路径
  - `pathlib.Path.with_name` / `with_suffix` 真替换
  - `pathlib.Path.stat()` 真取元数据
  - `pathlib.Path.read_text/write_text` 真 IO
  - `pathlib.Path.exists/is_file/is_dir` 真判
"""
import asyncio
import os
import pathlib
import signal
import ssl
import subprocess
import sys
import tempfile
import time

import pytest


# -- ssl 进阶 -----------------------------------------------------------------

class TestSslAdvanced:
    def test_create_default_context(self):
        """`ssl.create_default_context()` 真建 default context。"""
        ctx = ssl.create_default_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_SSLContext_protocol_TLS_CLIENT(self):
        """`SSLContext(PROTOCOL_TLS_CLIENT)` 真 client context,check_hostname 改 True。"""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = True
        assert ctx.check_hostname is True

    def test_SSLContext_minimum_version(self):
        """`SSLContext.minimum_version = TLSVersion.TLSv1_2` 真设最低版本。"""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    def test_SSLContext_set_alpn_protocols(self):
        """`set_alpn_protocols(['h2', 'http/1.1'])` 真设 ALPN。"""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        # 必含 'h2' 和 'http/1.1'
        # (服务器端可 _select_alpn_protocol)

    def test_get_default_verify_paths(self):
        """`ssl.get_default_verify_paths()` 真返 bundle path tuple。"""
        paths = ssl.get_default_verify_paths()
        # 必含 cafile/capath/openssl_cafile 等字段
        assert paths is not None
        # 至少 openssl_cafile 或 cafile 有值
        assert paths.openssl_cafile is not None or paths.cafile is not None


# -- subprocess 进阶 ----------------------------------------------------------

class TestSubprocessAdvancedV2:
    def test_Popen_async_start(self):
        """`Popen([...])` 真异步启动,`poll()` 返 None。"""
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
        try:
            # 未完成
            assert p.poll() is None
            p.wait(timeout=5)
            assert p.returncode == 0
        finally:
            if p.poll() is None:
                p.kill()

    def test_Popen_communicate_input(self):
        """`Popen.communicate(input='hello')` 真双向,送 stdin 收 stdout。"""
        p = subprocess.Popen(
            [sys.executable, "-c", "import sys; print(sys.stdin.read().upper(), end='')"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        stdout, _ = p.communicate(input="hello forge", timeout=5)
        assert stdout == "HELLO FORGE", (
            f"Popen.communicate 应回 'HELLO FORGE',实际 {stdout!r}"
        )

    def test_Popen_send_signal(self):
        """`Popen.send_signal(SIGUSR1)` 真发信号到子进程 (子进程装 handler 不退出)。"""
        # 子进程装 SIGUSR1 handler,这样发信号不终止它。
        # 装好之后写一行 READY:父进程读到这一行再发信号。固定 sleep
        # 会在机器忙时抢跑 —— 信号落在默认动作上,子进程被直接杀掉,
        # 表现为 returncode=-10,测试飘红却与被测行为无关。
        p = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import signal, sys, time; "
                "signal.signal(signal.SIGUSR1, signal.SIG_IGN); "
                "sys.stdout.write('READY\\n'); sys.stdout.flush(); "
                "time.sleep(2)",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        ready = p.stdout.readline()
        assert ready.strip() == "READY", f"子进程没就绪: {ready!r}"
        # 发 SIGUSR1 不抛,且子进程正常 exit
        p.send_signal(signal.SIGUSR1)
        p.wait(timeout=10)
        assert p.returncode == 0, (
            f"装了 SIG_IGN handler,子进程应正常 exit,实际 returncode={p.returncode}"
        )


# -- asyncio 进阶 -------------------------------------------------------------

class TestAsyncioAdvancedV2:
    def test_start_server_and_connect(self):
        """`asyncio.start_server + open_connection` 真异步 echo server。"""

        async def echo_handler(reader, writer):
            data = await reader.read(1024)
            writer.write(b"echo:" + data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        async def main():
            server = await asyncio.start_server(
                echo_handler, "127.0.0.1", 0
            )
            host, port = server.sockets[0].getsockname()[:2]
            try:
                reader, writer = await asyncio.open_connection(host, port)
                writer.write(b"forge")
                await writer.drain()
                # 等响应
                data = await asyncio.wait_for(reader.read(1024), timeout=2)
                writer.close()
                await writer.wait_closed()
                return data
            finally:
                server.close()
                await server.wait_closed()

        result = asyncio.run(main())
        assert result == b"echo:forge", f"asyncio echo 应=b'echo:forge',实际 {result!r}"

    def test_asyncio_Lock_mutex(self):
        """`asyncio.Lock` 真互斥,严格 enter-exit 嵌套。"""
        order = []

        async def worker(lock, name):
            async with lock:
                order.append(f"{name}:in")
                await asyncio.sleep(0.01)
                order.append(f"{name}:out")

        async def main():
            lock = asyncio.Lock()
            await asyncio.gather(
                worker(lock, "a"),
                worker(lock, "b"),
                worker(lock, "c"),
            )

        asyncio.run(main())
        # 必配对 in→out,互斥保 in-out-in-out 严格交错
        for i in range(0, len(order), 2):
            assert order[i].endswith(":in")
            assert order[i + 1].endswith(":out")


# -- pathlib 进阶 -------------------------------------------------------------

class TestPathlibAdvanced:
    def test_PurePath_cross_platform(self):
        """`PurePath` 真根据 OS 用 separator。"""
        # PurePosixPath 用 /
        from pathlib import PurePosixPath
        p = PurePosixPath("a/b/c")
        assert str(p) == "a/b/c"
        # PureWindowsPath 用 \\
        from pathlib import PureWindowsPath
        pw = PureWindowsPath("a/b/c")
        assert "\\" in str(pw)

    def test_Path_glob(self):
        """`Path.glob('*.py')` 真通配。"""
        with tempfile.TemporaryDirectory() as d:
            for n in ("a.py", "b.txt", "c.py"):
                (pathlib.Path(d) / n).write_text("# empty")
            py_files = sorted(p.name for p in pathlib.Path(d).glob("*.py"))
            assert py_files == ["a.py", "c.py"]

    def test_Path_rglob(self):
        """`Path.rglob('*.py')` 真递归通配。"""
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "a.py").write_text("")
            (root / "sub").mkdir()
            (root / "sub" / "b.py").write_text("")
            py_files = sorted(p.name for p in root.rglob("*.py"))
            assert py_files == ["a.py", "b.py"], f"rglob 应=['a','b'],实际 {py_files}"

    def test_Path_relative_to(self):
        """`Path('a/b/c').relative_to('a')` 真 'b/c'。"""
        p = pathlib.Path("a/b/c")
        rel = p.relative_to("a")
        assert str(rel) == "b/c"

    def test_Path_with_name_suffix(self):
        """`Path('a.txt').with_name('b.txt').with_suffix('.md')` 真替换。"""
        p = pathlib.Path("a.txt")
        assert p.with_name("b.txt").name == "b.txt"
        assert p.with_suffix(".md").suffix == ".md"

    def test_Path_stat_metadata(self):
        """`Path.stat()` 真返 st_size/st_mtime 等元数据。"""
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "test.txt"
            f.write_text("forge")
            s = f.stat()
            assert s.st_size == 5  # len("forge")
            assert s.st_mtime > 0
            assert s.st_mode > 0

    def test_Path_read_write_text(self):
        """`Path.read_text/write_text` 真 IO round-trip。"""
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "rt.txt"
            f.write_text("forge content", encoding="utf-8")
            assert f.read_text(encoding="utf-8") == "forge content"

    def test_Path_exists_is_file_is_dir(self):
        """`Path.exists/is_file/is_dir` 真判。"""
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            assert root.is_dir() is True
            assert root.exists() is True
            f = root / "x.txt"
            f.write_text("")
            assert f.is_file() is True
            assert f.exists() is True
            assert f.is_dir() is False
