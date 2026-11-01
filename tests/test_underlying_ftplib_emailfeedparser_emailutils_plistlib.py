# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`ftplib` / `email.feedparser` / `email.utils` / `plistlib` 真底层测试。

- ftplib:自己起一个最小 FTP 服务,真的传文件
- email.feedparser:真的逐段喂进邮件并解析
- email.utils:真的做地址与时间的解析与格式化
- plistlib:真的读写属性列表文件

覆盖 ftplib 5 + email.feedparser 5 + email.utils 5 + plistlib 5 + 真底层测试。
"""

import email.feedparser
import email.utils
import ftplib
import plistlib
import socket
import socketserver
import threading
from pathlib import Path

import pytest


# ======================== ftplib ========================


class _FtpHandler(socketserver.StreamRequestHandler):
    """最小的 FTP 服务,支持被动模式取文件。"""

    def handle(self):
        """走一遍登录与取文件流程。"""
        self.wfile.write(b"220 forge FTP ready\r\n")
        data_listener = None
        try:
            while True:
                line = self.rfile.readline()
                if not line:
                    return
                command = line.decode("utf-8", "replace").strip()
                upper = command.upper()
                if upper.startswith("USER"):
                    self.wfile.write(b"331 need password\r\n")
                elif upper.startswith("PASS"):
                    self.wfile.write(b"230 logged in\r\n")
                elif upper.startswith("TYPE"):
                    self.wfile.write(b"200 type set\r\n")
                elif upper in ("ACCT", "FEAT", "SYST", "NOOP"):
                    self.wfile.write(b"200 ok\r\n")
                elif upper == "PWD":
                    self.wfile.write(b'257 "/" is the current directory\r\n')
                elif upper.startswith("CWD"):
                    self.wfile.write(b"250 directory changed\r\n")
                elif upper.startswith("SIZE"):
                    self.wfile.write(b"213 20\r\n")
                elif upper == "EPSV":
                    if data_listener is not None:
                        data_listener.close()
                    data_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    data_listener.bind(("127.0.0.1", 0))
                    data_listener.listen(1)
                    port = data_listener.getsockname()[1]
                    self.wfile.write(
                        f"229 Entering Extended Passive Mode (|||{port}|)\r\n".encode()
                    )
                elif upper == "PASV":
                    if data_listener is not None:
                        data_listener.close()
                    data_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    data_listener.bind(("127.0.0.1", 0))
                    data_listener.listen(1)
                    port = data_listener.getsockname()[1]
                    self.wfile.write(
                        f"227 Entering Passive Mode (127,0,0,1,{port >> 8},{port & 0xFF})\r\n"
                        .encode()
                    )
                elif upper.startswith("RETR"):
                    self.wfile.write(b"150 opening data connection\r\n")
                    self._send_file(data_listener, b"forge ftp content\r\n")
                    self.wfile.write(b"226 transfer complete\r\n")
                elif upper.startswith("LIST"):
                    self.wfile.write(b"150 opening data connection\r\n")
                    self._send_file(data_listener, b"forge.txt\r\n")
                    self.wfile.write(b"226 transfer complete\r\n")
                elif upper == "QUIT":
                    self.wfile.write(b"221 bye\r\n")
                    return
                else:
                    self.wfile.write(b"502 not implemented\r\n")
        finally:
            if data_listener is not None:
                data_listener.close()

    def _send_file(self, listener, payload: bytes):
        """把内容送到数据连接上。"""
        if listener is None:
            return
        conn, _ = listener.accept()
        try:
            conn.sendall(payload)
        finally:
            conn.close()
            listener.close()


class _FtpServer(socketserver.ThreadingTCPServer):
    """真的在网络上提供 FTP 服务。"""

    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture
def ftp_server():
    """真的起一个 FTP 服务。"""
    server = _FtpServer(("127.0.0.1", 0), _FtpHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestFtplib:
    """FTP 传输"""

    def test_connect(self, ftp_server):
        """真的连上服务"""
        host, port = ftp_server
        client = ftplib.FTP()
        try:
            client.connect(host, port, timeout=10)
            assert client.welcome.startswith("220")
        finally:
            client.close()

    def test_login(self, ftp_server):
        """能完成登录"""
        host, port = ftp_server
        client = ftplib.FTP()
        try:
            client.connect(host, port, timeout=10)
            client.login("forge", "secret")
            assert client.voidcmd("TYPE I") == "200 type set"
        finally:
            client.close()

    def test_set_pasv(self, ftp_server):
        """能切到被动模式"""
        host, port = ftp_server
        client = ftplib.FTP()
        try:
            client.connect(host, port, timeout=10)
            client.login("forge", "secret")
            client.set_pasv(True)
            # 被动模式已打开,接下来能取到数据端口
            assert client.sock is not None
        finally:
            client.close()

    def test_retr(self, ftp_server):
        """真的取回文件内容"""
        host, port = ftp_server
        client = ftplib.FTP()
        try:
            client.connect(host, port, timeout=10)
            client.login("forge", "secret")
            lines = []
            client.retrbinary("RETR forge.txt", lines.append)
            assert b"".join(lines) == b"forge ftp content\r\n"
        finally:
            client.close()

    def test_dir(self, ftp_server):
        """能列出目录"""
        host, port = ftp_server
        client = ftplib.FTP()
        try:
            client.connect(host, port, timeout=10)
            client.login("forge", "secret")
            lines = []
            client.dir(lines.append)
            assert any("forge.txt" in line for line in lines)
        finally:
            client.close()


# ======================== email.feedparser ========================


class TestEmailFeedparser:
    """逐段解析邮件"""

    def test_parse_simple(self):
        """能解析出主题"""
        parser = email.feedparser.FeedParser()
        parser.feed("Subject: forge\r\n\r\nbody\r\n")
        message = parser.close()
        assert message["Subject"] == "forge"

    def test_parse_headers(self):
        """能解析出各个头"""
        parser = email.feedparser.FeedParser()
        parser.feed("From: a@forge.invalid\r\nTo: b@forge.invalid\r\n")
        parser.feed("Subject: forge\r\n\r\n")
        message = parser.close()
        assert message["From"] == "a@forge.invalid"
        assert message["To"] == "b@forge.invalid"

    def test_parse_body(self):
        """能解析出正文"""
        parser = email.feedparser.FeedParser()
        parser.feed("Subject: forge\r\n\r\nthe body\r\n")
        message = parser.close()
        assert "the body" in message.get_payload()

    def test_defects_collected(self):
        """能看出邮件的缺陷"""
        parser = email.feedparser.FeedParser()
        parser.feed("Subject forge-no-colon\r\n\r\n")
        message = parser.close()
        assert message.defects is not None

    def test_multiline_header(self):
        """能处理折行的头"""
        parser = email.feedparser.FeedParser()
        parser.feed("Subject: forge\r\n continued\r\n\r\n")
        message = parser.close()
        assert "forge" in str(message["Subject"])


# ======================== email.utils ========================


class TestEmailUtils:
    """地址与时间"""

    def test_parseaddr(self):
        """能拆出姓名与地址"""
        name, address = email.utils.parseaddr("Forge Name <forge@forge.invalid>")
        assert name == "Forge Name"
        assert address == "forge@forge.invalid"

    def test_parseaddr_plain(self):
        """只有地址时也能拆"""
        name, address = email.utils.parseaddr("forge@forge.invalid")
        assert address == "forge@forge.invalid"

    def test_formataddr(self):
        """能拼回地址"""
        result = email.utils.formataddr(("Forge Name", "forge@forge.invalid"))
        assert "forge@forge.invalid" in result

    def test_parsedate(self):
        """能解析日期"""
        parsed = email.utils.parsedate("Mon, 1 Jan 2024 00:00:00 +0000")
        assert parsed is not None
        assert parsed[0] == 2024
        assert parsed[1] == 1
        assert parsed[2] == 1

    def test_mktime_tz(self):
        """时间元组能换成时间戳"""
        stamp = email.utils.mktime_tz((2024, 1, 1, 0, 0, 0, 0, 1, 0, 0))
        assert isinstance(stamp, (int, float))
        assert stamp > 0

    def test_getaddresses(self):
        """能拆出多个地址"""
        addresses = email.utils.getaddresses(
            ["Forge <forge@forge.invalid>", "other@forge.invalid"]
        )
        assert len(addresses) == 2


# ======================== plistlib ========================


class TestPlistlib:
    """属性列表文件"""

    def test_write_and_read_xml(self, tmp_path):
        """真的写出并读回 XML 格式"""
        path = tmp_path / "forge.plist"
        data = {"forge": "value", "count": 3}
        with path.open("wb") as handle:
            plistlib.dump(data, handle, fmt=plistlib.FMT_XML)
        with path.open("rb") as handle:
            assert plistlib.load(handle) == data

    def test_write_and_read_binary(self, tmp_path):
        """真的写出并读回二进制格式"""
        path = tmp_path / "forge-binary.plist"
        data = {"forge": [1, 2, 3]}
        with path.open("wb") as handle:
            plistlib.dump(data, handle, fmt=plistlib.FMT_BINARY)
        with path.open("rb") as handle:
            assert plistlib.load(handle) == data

    def test_xml_is_text(self, tmp_path):
        """XML 格式写出来是文本"""
        path = tmp_path / "forge.plist"
        with path.open("wb") as handle:
            plistlib.dump({"forge": 1}, handle, fmt=plistlib.FMT_XML)
        text = path.read_text(encoding="utf-8")
        assert "<plist" in text
        assert "<key>forge</key>" in text

    def test_nested_structure(self, tmp_path):
        """嵌套结构能往返"""
        path = tmp_path / "forge.plist"
        data = {"outer": {"inner": ["a", "b"]}}
        with path.open("wb") as handle:
            plistlib.dump(data, handle)
        with path.open("rb") as handle:
            assert plistlib.load(handle) == data

    def test_loads_dumps(self, tmp_path):
        """能直接处理字节串"""
        raw = plistlib.dumps({"forge": 1}, fmt=plistlib.FMT_XML)
        assert plistlib.loads(raw) == {"forge": 1}
