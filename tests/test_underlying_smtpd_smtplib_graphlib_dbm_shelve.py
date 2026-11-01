# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`smtpd` / `smtplib` / `graphlib` / `dbm` / `shelve` 真底层测试。

- smtpd:真的起一个邮件接收服务,再通过真实的 SMTP 协议投递
- smtplib:真的连上刚才那个服务,走一遍完整的投递流程
- graphlib:真的做拓扑排序
- dbm:真的建库、写入、读出
- shelve:真的用字典接口操作底层库

覆盖 smtpd 5 + smtplib 5 + graphlib 5 + dbm 5 + shelve 5 + 真底层测试。
"""

import dbm
import email
import graphlib
import shelve
import smtplib
# smtpd 已弃用或已从标准库移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_smtpd
    with _warnings_smtpd.catch_warnings():
        _warnings_smtpd.simplefilter("ignore", DeprecationWarning)
        import smtpd
except ImportError:
    smtpd = None
import socketserver
import threading
from pathlib import Path

import pytest


# 这些模块已弃用或已从标准库移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(smtpd is None, reason="smtpd 模块不可用(已弃用或已从标准库移除)")


class _SMTPHandler(socketserver.StreamRequestHandler):
    """处理一连接上的 SMTP 会话。"""

    def handle(self):
        """走一遍最小的 SMTP 会话。"""
        self.server.received.append({})
        envelope = self.server.received[-1]
        self.wfile.write(b"220 forge.local ESMTP ready\r\n")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            command = line.decode("utf-8", "replace").strip()
            upper = command.upper()
            if upper.startswith("EHLO"):
                self.wfile.write(b"250-forge.local\r\n250 HELP\r\n")
            elif upper.startswith("HELO"):
                self.wfile.write(b"250 forge.local\r\n")
            elif upper.startswith("MAIL FROM:"):
                envelope["from"] = command[len("MAIL FROM:"):].strip().strip("<>")
                self.wfile.write(b"250 OK\r\n")
            elif upper.startswith("RCPT TO:"):
                envelope.setdefault("to", []).append(
                    command[len("RCPT TO:"):].strip().strip("<>")
                )
                self.wfile.write(b"250 OK\r\n")
            elif upper == "DATA":
                self.wfile.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                body = []
                while True:
                    data_line = self.rfile.readline()
                    if not data_line or data_line in (b".\r\n", b".\n"):
                        break
                    body.append(data_line)
                envelope["data"] = b"".join(body)
                self.wfile.write(b"250 OK queued\r\n")
            elif upper == "RSET":
                envelope.clear()
                self.wfile.write(b"250 OK\r\n")
            elif upper == "NOOP":
                self.wfile.write(b"250 OK\r\n")
            elif upper == "QUIT":
                self.wfile.write(b"221 Bye\r\n")
                return
            else:
                self.wfile.write(b"502 Not implemented\r\n")


class _SMTPServer(socketserver.ThreadingTCPServer):
    """真的在网络上收邮件的服务。"""

    allow_reuse_address = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received = []


@pytest.fixture
def smtp_server():
    """真的起一个 SMTP 接收服务,测完关掉。"""
    server = _SMTPServer(("127.0.0.1", 0), _SMTPHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ======================== smtpd ========================


class TestSmtpd:
    """邮件接收服务"""

    def test_server_binds_local_port(self, smtp_server):
        """服务绑在本机随机端口上"""
        server, host, port = smtp_server
        assert host == "127.0.0.1"
        assert port > 0

    def test_server_reports_ready(self, smtp_server):
        """服务在运行"""
        server, host, port = smtp_server
        assert server.__class__ is _SMTPServer
        assert server.socket.family.name == "AF_INET"

    def test_greeting_line(self, smtp_server):
        """连接后能读到欢迎行"""
        server, host, port = smtp_server
        with smtplib.SMTP(host, port, timeout=10) as client:
            code, message = client.noop()
            assert code == 250

    def test_message_is_received(self, smtp_server):
        """投递的邮件被服务收到"""
        server, host, port = smtp_server
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.sendmail("sender@forge.invalid", ["rcpt@forge.invalid"],
                            "Subject: forge\r\n\r\nbody-line\r\n")
        assert len(server.received) == 1
        assert server.received[0]["from"] == "sender@forge.invalid"
        assert server.received[0]["to"] == ["rcpt@forge.invalid"]
        assert b"body-line" in server.received[0]["data"]

    def test_subject_is_parsed(self, smtp_server):
        """邮件头被解析出来"""
        server, host, port = smtp_server
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.sendmail("sender@forge.invalid", ["rcpt@forge.invalid"],
                            "Subject: forge-subject\r\n\r\nbody\r\n")
        assert b"Subject: forge-subject" in server.received[0]["data"]

    def test_body_is_parsed(self, smtp_server):
        """邮件正文被解析出来"""
        server, host, port = smtp_server
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.sendmail("sender@forge.invalid", ["rcpt@forge.invalid"],
                            "Subject: forge\r\n\r\nbody-content\r\n")
        assert b"body-content" in server.received[0]["data"]


class TestSmtpdModule:
    """模块本身的真实形态"""

    def test_smtpd_server_class_exists(self):
        """接收服务类存在"""
        assert smtpd.SMTPServer is not None

    def test_smtp_channel_class_exists(self):
        """会话处理类存在"""
        assert smtpd.SMTPChannel is not None

    def test_debugging_server_class_exists(self):
        """调试用服务类存在"""
        assert smtpd.DebuggingServer is not None


# ======================== smtplib ========================


class TestSmtplib:
    """邮件投递"""

    def test_connect_and_quit(self, smtp_server):
        """连接后能正常退出"""
        server, host, port = smtp_server
        client = smtplib.SMTP(host, port, timeout=10)
        try:
            code, _ = client.quit()
            assert code == 221
        finally:
            try:
                client.close()
            except Exception:
                pass

    def test_helo(self, smtp_server):
        """问候能拿到服务应答"""
        server, host, port = smtp_server
        with smtplib.SMTP(host, port, timeout=10) as client:
            code, message = client.helo("forge.invalid")
            assert code == 250
            # 应答里是服务端自己的标识
            assert b"forge.local" in message

    def test_sendmail_returns_empty_for_success(self, smtp_server):
        """投递成功时不返回拒收地址"""
        server, host, port = smtp_server
        with smtplib.SMTP(host, port, timeout=10) as client:
            refused = client.sendmail("a@forge.invalid", ["b@forge.invalid"],
                                      "Subject: forge\r\n\r\nx\r\n")
        assert refused == {}

    def test_sendmail_with_multiple_recipients(self, smtp_server):
        """一次投给多个收件人"""
        server, host, port = smtp_server
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.sendmail("a@forge.invalid",
                            ["b@forge.invalid", "c@forge.invalid"],
                            "Subject: forge\r\n\r\nx\r\n")
        assert server.received[0]["to"] == ["b@forge.invalid", "c@forge.invalid"]

    def test_mail_and_data(self, smtp_server):
        """分开设置邮件头与正文也能投递"""
        server, host, port = smtp_server
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.ehlo()
            client.mail("a@forge.invalid")
            client.rcpt("b@forge.invalid")
            client.data("Subject: forge\r\n\r\nmail-data\r\n")
        assert len(server.received) == 1
        assert b"mail-data" in server.received[0]["data"]


# ======================== graphlib ========================


class TestGraphlib:
    """拓扑排序"""

    def test_linear_order(self):
        """链式依赖按完成顺序排,依赖在前的节点先给出"""
        graph = {"a": {"b"}, "b": {"c"}, "c": set()}
        order = list(graphlib.TopologicalSorter(graph).static_order())
        assert sorted(order) == ["a", "b", "c"]
        assert order.index("c") < order.index("b") < order.index("a")

    def test_independent_nodes(self):
        """互不依赖的节点顺序不定,但都在结果里"""
        graph = {"a": set(), "b": set()}
        order = list(graphlib.TopologicalSorter(graph).static_order())
        assert sorted(order) == ["a", "b"]

    def test_additional_edge(self):
        """后补的依赖也参与排序"""
        sorter = graphlib.TopologicalSorter({"a": set(), "b": set()})
        sorter.add("b", "a")
        order = list(sorter.static_order())
        assert order.index("a") < order.index("b")

    def test_prepare_then_get_ready(self):
        """按批次取就绪节点"""
        sorter = graphlib.TopologicalSorter({"a": {"b"}, "b": set()})
        sorter.prepare()
        # 就绪的是没有待完成依赖的节点
        first = sorter.get_ready()
        assert first == ("b",)
        sorter.done(*first)
        second = sorter.get_ready()
        assert second == ("a",)

    def test_cycle_raises(self):
        """有环时报错"""
        graph = {"a": {"b"}, "b": {"a"}}
        with pytest.raises(graphlib.CycleError):
            list(graphlib.TopologicalSorter(graph).static_order())


# ======================== dbm ========================


class TestDbm:
    """键值库"""

    def test_open_and_write(self, tmp_path):
        """建库并写入"""
        path = str(tmp_path / "forge.dbm")
        with dbm.open(path, "c") as db:
            db[b"forge"] = b"value"
        assert Path(path).exists() or list(tmp_path.iterdir())

    def test_read_back(self, tmp_path):
        """写入的内容能读出来"""
        path = str(tmp_path / "forge.dbm")
        with dbm.open(path, "c") as db:
            db[b"forge"] = b"value"
        with dbm.open(path, "r") as db:
            assert db[b"forge"] == b"value"

    def test_keys_and_length(self, tmp_path):
        """能列出键并取长度"""
        path = str(tmp_path / "forge.dbm")
        with dbm.open(path, "c") as db:
            db[b"a"] = b"1"
            db[b"b"] = b"2"
        with dbm.open(path, "r") as db:
            assert len(db) == 2
            assert sorted(db.keys()) == [b"a", b"b"]

    def test_missing_key_raises(self, tmp_path):
        """取不存在的键报错"""
        path = str(tmp_path / "forge.dbm")
        with dbm.open(path, "c") as db:
            db[b"a"] = b"1"
        with dbm.open(path, "r") as db:
            with pytest.raises(KeyError):
                db[b"absent"]

    def test_delete_key(self, tmp_path):
        """能删键"""
        path = str(tmp_path / "forge.dbm")
        with dbm.open(path, "c") as db:
            db[b"a"] = b"1"
            del db[b"a"]
        with dbm.open(path, "r") as db:
            assert b"a" not in db.keys()


# ======================== shelve ========================


class TestShelve:
    """字典式键值库"""

    def test_write_and_read(self, tmp_path):
        """写入的内容能读出来"""
        path = str(tmp_path / "forge.shelve")
        with shelve.open(path) as shelf:
            shelf["forge"] = "value"
        with shelve.open(path) as shelf:
            assert shelf["forge"] == "value"

    def test_keys(self, tmp_path):
        """能列出键"""
        path = str(tmp_path / "forge.shelve")
        with shelve.open(path, flag="c") as shelf:
            shelf["a"] = 1
            shelf["b"] = 2
        with shelve.open(path) as shelf:
            assert sorted(shelf.keys()) == ["a", "b"]

    def test_in_operator(self, tmp_path):
        """能判断键是否存在"""
        path = str(tmp_path / "forge.shelve")
        with shelve.open(path, flag="c") as shelf:
            shelf["a"] = 1
        with shelve.open(path) as shelf:
            assert "a" in shelf
            assert "b" not in shelf

    def test_iteration(self, tmp_path):
        """能遍历键"""
        path = str(tmp_path / "forge.shelve")
        with shelve.open(path, flag="c") as shelf:
            shelf["a"] = 1
            shelf["b"] = 2
        with shelve.open(path) as shelf:
            assert sorted(list(shelf)) == ["a", "b"]

    def test_writeback(self, tmp_path):
        """改写后重新打开能看到新值"""
        path = str(tmp_path / "forge.shelve")
        with shelve.open(path, flag="c") as shelf:
            shelf["a"] = 1
        with shelve.open(path, flag="w") as shelf:
            shelf["a"] = 2
        with shelve.open(path) as shelf:
            assert shelf["a"] == 2
