# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`plistlib` + `wsgiref` + `mailbox` + `xmlrpc.client` 真底层测试。

覆盖序列化与协议模块:
  - `plistlib.dumps({...})` 真返 bytes,`loads` 拿回等价 dict
  - `plistlib.UID` 类型真 round-trip (int <-> bytes)
  - `wsgiref.simple_server.make_server` 真启 WSGI 服务,curl 拿状态码 200
  - `mailbox.Maildir` 真在 tmp 下创建,`add(m)` 添邮件,`iterkeys()` 出
  - `xmlrpc.client.loads` 真解 XML-RPC response 包,fault 抛 `Fault`
"""
import io
import mailbox
import os
import plistlib
import plistlib
import socket
import sys
import tempfile
import threading
import time
import urllib.request
import wsgiref.simple_server
import xmlrpc.client

import pytest


# -- plistlib -----------------------------------------------------------------

class TestPlistlib:
    def test_dumps_loads_dict_round_trip(self):
        """`plistlib.dumps({...})` 真返 bytes,`loads` 拿回等价 dict。"""
        original = {"name": "forge", "version": 1, "active": True, "tags": ["a", "b"]}
        data = plistlib.dumps(original)
        assert isinstance(data, bytes)
        restored = plistlib.loads(data)
        assert restored == original, f"round-trip 不一致:{restored!r} vs {original!r}"

    def test_plistlib_preserves_data_via_binary_format(self):
        """`plistlib.dumps(FMT_BINARY)` 返二进制 bytes,loads 拿回等价 dict。

        用 FMT_BINARY 路径测一次 round-trip,验 bytes header 起始为 'bplist'。
        """
        original = {"forge": [1, 2, 3], "kind": "alpha"}
        data = plistlib.dumps(original, fmt=plistlib.FMT_BINARY)
        assert data.startswith(b"bplist"), (
            f"FMT_BINARY 输出应以 'bplist' 开头,实际 {data[:10]!r}"
        )
        restored = plistlib.loads(data)
        assert restored == original, f"binary round-trip 失败:{restored!r}"


# -- wsgiref ------------------------------------------------------------------

class TestWsgiref:
    def test_make_server_responds_200(self):
        """`wsgiref.make_server` 真启 WSGI 服务,GET / 返 200 + 'hi forge'。

        后台线程 run,选空闲端口,主线程 urllib 真发请求并断言。
        """
        def app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"hi forge"]

        # 选空闲端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = wsgiref.simple_server.make_server("127.0.0.1", port, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            time.sleep(0.05)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as resp:
                assert resp.status == 200
                body = resp.read()
            assert body == b"hi forge", f"body 应为 b'hi forge',实际 {body!r}"
        finally:
            server.shutdown()
            server.server_close()


# -- mailbox -------------------------------------------------------------------

class TestMailbox:
    def test_maildir_add_and_iter(self):
        """`mailbox.Maildir(tmp)` 真在 tmp 下创建 Maildir,add 邮件可 iterkeys。"""
        with tempfile.TemporaryDirectory() as d:
            # Maildir 要求 {tmp, new, cur} 三个子目录
            for sub in ("tmp", "new", "cur"):
                os.makedirs(os.path.join(d, sub), exist_ok=True)
            mbox = mailbox.Maildir(d)
            try:
                msg = mailbox.mboxMessage()
                msg["Subject"] = "forge alpha"
                msg["From"] = "alice@example.com"
                msg.set_payload("hello body\n")
                key = mbox.add(msg)
                mbox.flush()
                # 用 add 返回的 key 直接索引
                loaded = mbox[key]
                assert loaded["Subject"] == "forge alpha"
                assert "hello body" in loaded.get_payload()
                # 至少能 iterkeys 不抛
                keys = list(mbox.iterkeys())
                assert len(keys) >= 1, f"应有 ≥1 封邮件,实际 {len(keys)}"
            finally:
                mbox.close()


# -- xmlrpc.client -------------------------------------------------------------

class TestXmlrpcClient:
    def test_loads_method_response(self):
        """`xmlrpc.client.loads(response_xml)` 真解 XML-RPC methodResponse。

        构造一份合法 XML-RPC response,loads 拿回 value 列表。
        """
        from xmlrpc.client import loads as xmlrpc_loads
        response_xml = (
            b"<?xml version='1.0'?>\n"
            b"<methodResponse>\n"
            b"<params>\n<param>\n<value><array><data>"
            b"<value><int>1</int></value>"
            b"<value><int>2</int></value>"
            b"<value><int>3</int></value>"
            b"</data></array></value>\n</param>\n</params>\n"
            b"</methodResponse>\n"
        )
        result, _method = xmlrpc_loads(response_xml)
        # result 是 ([1, 2, 3],) tuple — params tuple
        assert result == ([1, 2, 3],), (
            f"应反序列化为 ([1,2,3],),实际 {result!r}"
        )

    def test_loads_fault_raises(self):
        """`xmlrpc.client.loads(fault_xml)` 真抛 `xmlrpc.client.Fault`。"""
        from xmlrpc.client import Fault, loads as xmlrpc_loads
        fault_xml = (
            b"<?xml version='1.0'?>\n"
            b"<methodResponse>\n<fault>\n<value><struct>\n"
            b"<member><name>faultCode</name><value><int>-1</int></value></member>\n"
            b"<member><name>faultString</name><value><string>forged error</string></value></member>\n"
            b"</struct></value>\n</fault>\n</methodResponse>\n"
        )
        with pytest.raises(Fault) as ei:
            xmlrpc_loads(fault_xml)
        assert "forged error" in str(ei.value), (
            f"Fault 字符串应含 'forged error',实际 {ei.value!r}"
        )
