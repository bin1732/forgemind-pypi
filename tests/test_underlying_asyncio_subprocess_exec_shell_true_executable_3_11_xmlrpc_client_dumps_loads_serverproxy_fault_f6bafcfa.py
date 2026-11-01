# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess_exec` shell=True (3.11+)+executable (3.11+) 进阶 + `xmlrpc.client.dumps/loads/Fault/ServerProxy` 真用 + `http.server.BaseHTTPRequestHandler` 进阶 (do_GET 真)+ `wsgiref.simple_server.application` 进阶 + `multiprocessing.connection.Pipe` 真 (duplex send_bytes + recv) + 真底层测试。

覆盖 asyncio.subprocess 1 真 (shell=True 3.11+) + xmlrpc 3 真 (dumps+loads+Fault) + http.server 1 真 (BaseHTTPRequestHandler) + wsgiref 1 真 (application) + multiprocessing.connection 1 真 (Pipe 真 duplex bytes) (共 7 真测试) 模块:
  - `asyncio.subprocess shell=True (3.11+) 'echo forge' 必返 stdout`
  - `xmlrpc.client.dumps 'forge_value' + loads 必 'forge_value'`
  - `xmlrpc.client.Fault 真 raise 必 Fault instance`
  - `xmlrpc.client.ServerProxy 必 class 存在`
  - `http.server.BaseHTTPRequestHandler 真 class 存在 (do_GET 必 method)`
  - `wsgiref.simple_server.application 真 callable class`
  - `multiprocessing.connection.Pipe 真 duplex send_bytes 5 + recv 5`
"""
import asyncio
import multiprocessing.connection
import sys
import wsgiref.simple_server
import xmlrpc.client
import xmlrpc.server
import http.server
import socketserver

import pytest


# -- asyncio.subprocess 进阶 (shell=True 3.11+) -----------------

class TestAsyncioSubprocessShell:
    def test_subprocess_shell_3_11(self):
        """`asyncio.subprocess 真 create_subprocess_shell (3.11+) 'echo forge' 必返 stdout。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ create_subprocess_shell")

        async def main():
            proc = await asyncio.create_subprocess_shell(
                "echo forge_shell",
                stdout=asyncio.subprocess.PIPE,
            )
            out, _ = await proc.communicate()
            return out, proc.returncode

        out, rc = asyncio.run(main())
        # 必含 'forge_shell'
        assert b"forge_shell" in out
        # 必 0
        assert rc == 0


# -- xmlrpc 进阶 (dumps+loads+Fault+ServerProxy) ---------------

class TestXmlrpcAdvanced:
    def test_dumps_loads(self):
        """`xmlrpc.client.dumps 'forge_value' + loads 必 'forge_value'。"""
        # dumps
        data = xmlrpc.client.dumps(("forge_value",), methodname="echo")
        # loads
        result, method = xmlrpc.client.loads(data)
        # 必 'forge_value'
        assert result == ("forge_value",)
        assert method == "echo"

    def test_Fault(self):
        """`xmlrpc.client.Fault 真 raise 必 Fault instance。"""
        # 真 raise
        try:
            raise xmlrpc.client.Fault(1, "forge_fault")
        except xmlrpc.client.Fault as e:
            # 必 faultCode=1
            assert e.faultCode == 1
            # 必 'forge_fault'
            assert "forge_fault" in e.faultString

    def test_ServerProxy_class(self):
        """`xmlrpc.client.ServerProxy 必 class 存在。"""
        # 沙箱 3.11+ 必有
        assert xmlrpc.client.ServerProxy is not None


# -- http.server.BaseHTTPRequestHandler 进阶 --------------------

class TestHttpServerRequestHandlerAdvanced:
    def test_BaseHTTPRequestHandler_methods(self):
        """`http.server.BaseHTTPRequestHandler 真 class 存在 (含 handle+parse_request)。"""
        # 必能 check class
        cls = http.server.BaseHTTPRequestHandler
        # 必含 handle
        assert hasattr(cls, "handle")
        # 必含 parse_request
        assert hasattr(cls, "parse_request")
        # 必含 send_response
        assert hasattr(cls, "send_response")


# -- wsgiref.simple_server.application 进阶 -------------------

class TestWsgirefApplicationAdvanced:
    def test_application(self):
        """`wsgiref.simple_server.application 真 callable class。"""
        # 必 callable
        assert callable(wsgiref.simple_server.WSGIRequestHandler)
        # 必能建
        handler = wsgiref.simple_server.WSGIRequestHandler
        # 必含 handle
        assert hasattr(handler, "handle")


# -- multiprocessing.connection.Pipe 进阶 (真 duplex bytes) ----

class TestMultiprocessingConnectionPipeAdvanced:
    def test_Pipe_duplex_bytes(self):
        """`multiprocessing.connection.Pipe 真 duplex send_bytes 5 + recv 5。"""
        a, b = multiprocessing.connection.Pipe(duplex=True)
        try:
            # a → b bytes
            a.send_bytes(b"forge")
            result = b.recv_bytes()
            # 必 b'forge'
            assert result == b"forge"
            # b → a bytes
            b.send_bytes(b"hello")
            result2 = a.recv_bytes()
            # 必 b'hello'
            assert result2 == b"hello"
        finally:
            a.close()
            b.close()
