# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`poplib` / `nntplib` / `imp` / `mailbox` / `email.header` 真底层测试。

- poplib:自己起一个 POP3 服务,真的取信
- nntplib:自己起一个 NNTP 服务,真的取文章
- imp:真的按老式接口导入模块
- mailbox:真的读 mbox 邮件文件
- email.header:真的解析与构造邮件头

覆盖 poplib 5 + nntplib 5 + imp 4 + mailbox 5 + email.header 5 + 真底层测试。
"""

import email.header
import email.utils
# imp 在 Python 3.12 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_imp
    with _warnings_imp.catch_warnings():
        _warnings_imp.simplefilter("ignore", DeprecationWarning)
        import imp
except ImportError:
    imp = None
import mailbox
# nntplib 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import nntplib
except ImportError:
    nntplib = None
import poplib
import socket
import socketserver
import threading
from pathlib import Path

import pytest


# ======================== poplib ========================


# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(nntplib is None, reason="nntplib 模块在 Python 3.13 起被移除")


class _Pop3Handler(socketserver.StreamRequestHandler):
    """最小的 POP3 服务。"""

    MESSAGES = {
        1: b"Subject: forge one\r\n\r\nfirst body\r\n",
        2: b"Subject: forge two\r\n\r\nsecond body\r\n",
    }

    def handle(self):
        """走一遍取信流程。"""
        self.wfile.write(b"+OK forge POP3 ready\r\n")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            command = line.decode("utf-8", "replace").strip()
            upper = command.upper()
            if upper.startswith("USER"):
                self.wfile.write(b"+OK\r\n")
            elif upper.startswith("PASS"):
                self.wfile.write(b"+OK\r\n")
            elif upper == "STAT":
                self.wfile.write(b"+OK 2 30\r\n")
            elif upper == "LIST":
                self.wfile.write(b"+OK 2 messages\r\n1 10\r\n2 20\r\n.\r\n")
            elif upper.startswith("RETR"):
                index = int(command.split()[1])
                self.wfile.write(b"+OK\r\n" + self.MESSAGES[index] + b".\r\n")
            elif upper.startswith("TOP"):
                self.wfile.write(b"+OK\r\nSubject: forge top\r\n\r\n.\r\n")
            elif upper.startswith("DELE"):
                self.wfile.write(b"+OK\r\n")
            elif upper == "QUIT":
                self.wfile.write(b"+OK bye\r\n")
                return
            else:
                self.wfile.write(b"-ERR unknown\r\n")


class _Pop3Server(socketserver.ThreadingTCPServer):
    """真的在网络上提供 POP3 服务。"""

    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture
def pop3_server():
    """真的起一个 POP3 服务。"""
    server = _Pop3Server(("127.0.0.1", 0), _Pop3Handler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestPoplib:
    """POP3 取信"""

    def test_connect(self, pop3_server):
        """真的连上服务"""
        host, port = pop3_server
        client = poplib.POP3(host, port, timeout=10)
        try:
            assert client.welcome.startswith(b"+OK")
        finally:
            client.quit()

    def test_user_and_pass(self, pop3_server):
        """能完成登录"""
        host, port = pop3_server
        client = poplib.POP3(host, port, timeout=10)
        try:
            assert client.user("forge") is not None
            assert client.pass_("secret") is not None
        finally:
            client.quit()

    def test_stat(self, pop3_server):
        """能取到信箱统计"""
        host, port = pop3_server
        client = poplib.POP3(host, port, timeout=10)
        try:
            client.user("forge")
            client.pass_("secret")
            count, size = client.stat()
            assert count == 2
            assert size > 0
        finally:
            client.quit()

    def test_list(self, pop3_server):
        """能列出邮件"""
        host, port = pop3_server
        client = poplib.POP3(host, port, timeout=10)
        try:
            client.user("forge")
            client.pass_("secret")
            response, lines, octets = client.list()
            assert response.startswith(b"+OK")
            assert len(lines) == 2
            assert b"1 10" in lines
        finally:
            client.quit()

    def test_retr(self, pop3_server):
        """能取到邮件正文"""
        host, port = pop3_server
        client = poplib.POP3(host, port, timeout=10)
        try:
            client.user("forge")
            client.pass_("secret")
            response, lines, octets = client.retr(1)
            body = b"".join(lines)
            assert response.startswith(b"+OK")
            assert b"forge one" in body
            assert octets > 0
        finally:
            client.quit()


# ======================== nntplib ========================


class _NntpHandler(socketserver.StreamRequestHandler):
    """最小的 NNTP 服务。"""

    def handle(self):
        """走一遍取文章流程。"""
        self.wfile.write(b"200 forge NNTP ready\r\n")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            command = line.decode("utf-8", "replace").strip()
            upper = command.upper()
            if upper == "GROUP FORGE":
                self.wfile.write(b"211 1 1 1 forge.test\r\n")
            elif upper == "LIST":
                self.wfile.write(
                    b"215 1 articles\r\nforge.test 0000000001 0000000001 n\r\n.\r\n"
                )
            elif upper == "HEAD":
                self.wfile.write(b"221 1 forge.test\r\nSubject: forge head\r\n\r\n\r\n")
            elif upper.startswith("BODY"):
                self.wfile.write(b"222 1 forge.test\r\nforge body\r\n.\r\n")
            elif upper.startswith("STAT"):
                self.wfile.write(b"223 1 10\r\n")
            elif upper == "QUIT":
                self.wfile.write(b"205 bye\r\n")
                return
            else:
                self.wfile.write(b"500 unknown\r\n")


class _NntpServer(socketserver.ThreadingTCPServer):
    """真的在网络上提供 NNTP 服务。"""

    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture
def nntp_server():
    """真的起一个 NNTP 服务。"""
    server = _NntpServer(("127.0.0.1", 0), _NntpHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestNntplib:
    """NNTP 取文章"""

    def test_connect(self, nntp_server):
        """真的连上服务"""
        host, port = nntp_server
        client = nntplib.NNTP(host, port, timeout=10)
        try:
            assert client.welcome.startswith("200")
        finally:
            client.quit()

    def test_group(self, nntp_server):
        """能进入组"""
        host, port = nntp_server
        client = nntplib.NNTP(host, port, timeout=10)
        try:
            response, count, first, last, name = client.group("forge")
            assert response.startswith("211")
            assert count == 1
            assert name == "forge.test"
        finally:
            client.quit()

    def test_list(self, nntp_server):
        """能列出文章"""
        host, port = nntp_server
        client = nntplib.NNTP(host, port, timeout=10)
        try:
            client.group("forge")
            response, listing = client.list()
            assert response.startswith("215")
            assert len(listing) >= 1
            assert any("forge.test" in str(item) for item in listing)
        finally:
            client.quit()

    def test_body(self, nntp_server):
        """能取到文章正文"""
        host, port = nntp_server
        client = nntplib.NNTP(host, port, timeout=10)
        try:
            response, article = client.body(1)
            assert response.startswith("222")
            assert b"forge body" in b"".join(article.lines)
        finally:
            client.quit()

    def test_stat(self, nntp_server):
        """能取到文章统计"""
        host, port = nntp_server
        client = nntplib.NNTP(host, port, timeout=10)
        try:
            response, number, size = client.stat(1)
            assert response.startswith("223")
            assert number == 1
            assert int(size) > 0
        finally:
            client.quit()


# ======================== imp ========================


class TestImp:
    """老式导入接口"""

    def test_find_module(self):
        """能找到模块"""
        found = imp.find_module("json")
        assert found is not None
        assert found[0] is None
        assert found[1].endswith("json")

    def test_load_source(self):
        """能按老式接口载入源码文件"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "forge_imp_mod.py"
            source.write_text("VALUE = 'forge'\n", encoding="utf-8")
            module = imp.load_source("forge_imp_mod", str(source))
            assert module is not None
            assert module.VALUE == "forge"

    def test_get_suffixes(self):
        """能列出支持的扩展名"""
        suffixes = imp.get_suffixes()
        assert isinstance(suffixes, list)
        assert suffixes

    def test_acquire_lock_and_release(self):
        """能拿到并释放导入锁"""
        imp.acquire_lock()
        imp.release_lock()


# ======================== mailbox ========================


MBOX_TEXT = """From forge@forge.invalid Mon Jan  1 00:00:00 2024
Subject: first
From: forge@forge.invalid
To: rcpt@forge.invalid

first body

From forge@forge.invalid Tue Jan  2 00:00:00 2024
Subject: second
From: forge@forge.invalid
To: rcpt@forge.invalid

second body
"""


class TestMailbox:
    """mbox 邮件文件"""

    def _write(self, tmp_path: Path) -> Path:
        path = tmp_path / "forge.mbox"
        path.write_text(MBOX_TEXT, encoding="utf-8")
        return path

    def test_iterates_messages(self, tmp_path):
        """能读出邮件数"""
        path = self._write(tmp_path)
        box = mailbox.mbox(str(path))
        try:
            assert len(box) == 2
        finally:
            box.close()

    def test_subject(self, tmp_path):
        """能取到邮件主题"""
        path = self._write(tmp_path)
        box = mailbox.mbox(str(path))
        try:
            assert box[0]["Subject"] == "first"
            assert box[1]["Subject"] == "second"
        finally:
            box.close()

    def test_sender(self, tmp_path):
        """能取到发件人"""
        path = self._write(tmp_path)
        box = mailbox.mbox(str(path))
        try:
            assert box[0]["From"] == "forge@forge.invalid"
        finally:
            box.close()

    def test_body(self, tmp_path):
        """能取到正文"""
        path = self._write(tmp_path)
        box = mailbox.mbox(str(path))
        try:
            payload = box[0].get_payload()
            assert "first body" in payload
        finally:
            box.close()

    def test_keys(self, tmp_path):
        """能列出邮件头字段"""
        path = self._write(tmp_path)
        box = mailbox.mbox(str(path))
        try:
            assert "Subject" in box[0].keys()
        finally:
            box.close()


# ======================== email.header ========================


class TestEmailHeader:
    """邮件头解析与构造"""

    def test_make_header(self):
        """能构造邮件头"""
        header = email.header.make_header([("forge", "utf-8")])
        assert "forge" in str(header)

    def test_decode_header(self):
        """能解码编码过的邮件头"""
        value = "=?utf-8?b?Zm9yZ2U=?="
        parts = email.header.decode_header(value)
        assert parts

    def test_header_equals_str(self):
        """邮件头对象能当字符串用"""
        header = email.header.Header("forge 中文", "utf-8")
        assert "forge" in str(header)

    def test_header_encode(self):
        """邮件头能编码"""
        header = email.header.Header("forge", "utf-8")
        encoded = header.encode()
        assert isinstance(encoded, str)

    def test_formataddr(self):
        """能拼出地址与姓名"""
        result = email.utils.formataddr(("Forge Name", "forge@forge.invalid"))
        assert "forge@forge.invalid" in result
        assert "Forge Name" in result
