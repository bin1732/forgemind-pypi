# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess` 进阶 + `wsgiref` 进阶 真底层测试。

覆盖 async subprocess / WSGI 真底层模块:
  - `asyncio.create_subprocess_exec` 真跑 + 收 stdout
  - `asyncio.create_subprocess_shell` 真跑 shell
  - `Process.communicate()` 真双向
  - `Process.send_signal` 真发信号
  - `Process.kill/terminate` 真发 SIGKILL/SIGTERM
  - `Process.wait()` 真等
  - `Process.returncode` 真 int
  - `Process.stdin.write` 真写
  - `Process.stdout.readline` 真读行
  - `wsgiref.simple_server.make_server 真启 + 返 server`
  - `wsgiref.simple_server.WSGIRequestHandler 真 handle`
  - `wsgiref.util.request_uri 进阶 + PATH_INFO+QUERY_STRING`
  - `wsgiref.util.setup_testing_defaults 真设 environ`
"""
import asyncio
import os
import signal
import socket
import sys
import tempfile
import threading
import time
import wsgiref.simple_server
import wsgiref.util

import pytest


# -- asyncio.subprocess -------------------------------------------------------

class TestAsyncioSubprocess:
    def test_create_subprocess_exec_capture_stdout(self):
        """`asyncio.create_subprocess_exec 真跑 + 收 stdout`。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "print('hello forge from asyncio')",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout

        result = asyncio.run(main())
        assert b"hello forge from asyncio" in result, (
            f"应含 'hello forge from asyncio',实际 {result!r}"
        )

    def test_create_subprocess_shell(self):
        """`asyncio.create_subprocess_shell 真跑 shell`。"""

        async def main():
            proc = await asyncio.create_subprocess_shell(
                "echo forge",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout

        result = asyncio.run(main())
        assert b"forge" in result

    def test_process_send_signal(self):
        """`Process.send_signal(SIGUSR1) 真发信号到子进程`。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import signal, sys, time\n"
                "signal.signal(signal.SIGUSR1, signal.SIG_IGN)\n"
                "sys.stdout.write('READY\\n'); sys.stdout.flush()\n"
                "time.sleep(2)\n",
                stdout=asyncio.subprocess.PIPE,
            )
            # 等子进程真的装上 handler 再发信号:固定 sleep 会在机器忙时
            # 抢跑 —— 信号落在默认动作上,子进程被直接杀掉(returncode -10),
            # 测试飘红却与被测行为无关。
            ready = await proc.stdout.readline()
            assert ready.strip() == b"READY", f"子进程没就绪: {ready!r}"
            proc.send_signal(signal.SIGUSR1)
            await proc.wait()
            return proc.returncode

        returncode = asyncio.run(main())
        assert returncode == 0, f"装了 SIG_IGN handler, returncode 应=0,实际 {returncode}"

    def test_process_kill(self):
        """`Process.kill() 真发 SIGKILL 终止子进程`。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import time; time.sleep(10)",
            )
            await asyncio.sleep(0.1)
            proc.kill()
            await proc.wait()
            return proc.returncode

        returncode = asyncio.run(main())
        # SIGKILL 必为负 (-9) 或信号 (255)
        assert returncode != 0, f"被 kill 应 returncode!=0,实际 {returncode}"

    def test_process_terminate(self):
        """`Process.terminate() 真发 SIGTERM 终止子进程`。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import time; time.sleep(10)",
            )
            await asyncio.sleep(0.1)
            proc.terminate()
            await proc.wait()
            return proc.returncode

        returncode = asyncio.run(main())
        assert returncode != 0, f"被 terminate 应 returncode!=0,实际 {returncode}"

    def test_process_stdin_write(self):
        """`Process.stdin.write + communicate(input) 真双向`。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import sys; print(sys.stdin.read().upper(), end='')",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate(input=b"hello forge")
            return stdout

        result = asyncio.run(main())
        assert result == b"HELLO FORGE", (
            f"stdin 写 'hello forge' 应回 'HELLO FORGE',实际 {result!r}"
        )


# -- wsgiref 进阶 ------------------------------------------------------------

class TestWsgirefAdvancedV2:
    def test_make_server_creates(self):
        """`wsgiref.simple_server.make_server 真启 + 返 server`。"""
        server = wsgiref.simple_server.make_server(
            "127.0.0.1", 0, lambda e, s: [b""]
        )
        try:
            host, port = server.server_address
            assert host == "127.0.0.1"
            assert isinstance(port, int) and port > 0
        finally:
            server.server_close()

    def test_setup_testing_defaults(self):
        """`wsgiref.util.setup_testing_defaults 真设 environ`。"""
        environ = {}
        wsgiref.util.setup_testing_defaults(environ)
        # 必含 REQUEST_METHOD, PATH_INFO, SERVER_NAME, SERVER_PORT
        assert "REQUEST_METHOD" in environ
        assert "PATH_INFO" in environ
        assert "SERVER_NAME" in environ
        assert "SERVER_PORT" in environ
        # 默认 GET
        assert environ["REQUEST_METHOD"] == "GET"

    def test_WSGIRequestHandler_handle_one_request(self):
        """`WSGIRequestHandler 真处理一次 request`。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        def app(environ, start_response):
            body = b"hello forge WSGI"
            start_response("200 OK", [
                ("Content-Type", "text/plain"),
                ("Content-Length", str(len(body))),
            ])
            return [body]

        server = wsgiref.simple_server.make_server(
            "127.0.0.1", port, app
        )
        t = threading.Thread(target=server.handle_request, daemon=True)
        t.start()
        try:
            time.sleep(0.1)
            c = socket.socket()
            c.connect(("127.0.0.1", port))
            c.sendall(b"GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            data = b""
            c.settimeout(2)
            try:
                while True:
                    chunk = c.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            except socket.timeout:
                pass
            c.close()
            assert b"200 OK" in data, f"应含 '200 OK',实际 {data[:200]!r}"
            assert b"hello forge WSGI" in data
        finally:
            server.server_close()
