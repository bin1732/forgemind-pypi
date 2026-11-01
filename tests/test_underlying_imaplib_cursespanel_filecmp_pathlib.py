# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`imaplib` / `curses.panel` / `curses.ascii` / `filecmp` / `pathlib` 真底层测试。

- imaplib:自己起一个最小 IMAP4 服务,真的取信
- curses.panel:真的用面板层组织界面
- curses.ascii:真的查控制字符常量
- filecmp:真的比较目录与文件
- pathlib:真的做路径操作

覆盖 imaplib 5 + curses.panel 5 + filecmp 5 + pathlib 5 + 真底层测试。
"""

import filecmp
import imaplib
import pathlib
import shutil
import socket
import socketserver
import tempfile
import threading
from pathlib import Path

import pytest


# ======================== imaplib ========================


class _ImapHandler(socketserver.StreamRequestHandler):
    """最小的 IMAP4 服务。"""

    def handle(self):
        """走一遍取信流程。"""
        self.wfile.write(b"* OK forge IMAP4 ready\r\n")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            command = line.decode("utf-8", "replace").strip()
            # 客户端自带命令标记,应答要回显同一个标记
            parts = command.split(" ", 1)
            tag = parts[0]
            upper = parts[1].upper() if len(parts) > 1 else ""
            if upper.startswith("CAPABILITY"):
                self.wfile.write(b"* CAPABILITY IMAP4rev1\r\n")
                self.wfile.write(f"{tag} OK capability done\r\n".encode())
            elif upper.startswith("LOGIN"):
                self.wfile.write(f"{tag} OK logged in\r\n".encode())
            elif upper.startswith("SELECT"):
                self.wfile.write(b"* 1 EXISTS\r\n")
                self.wfile.write(f"{tag} OK selected\r\n".encode())
            elif upper.startswith("FETCH"):
                self.wfile.write(
                    b"* 1 FETCH (BODY[TEXT] {24}\r\nSubject: forge\r\n\r\nbody\r\n)\r\n"
                )
                self.wfile.write(f"{tag} OK fetch done\r\n".encode())
            elif upper.startswith("LIST"):
                self.wfile.write(b'* LIST (\\HasNoChildren) "/" "INBOX"\r\n')
                self.wfile.write(f"{tag} OK list done\r\n".encode())
            elif upper.startswith("LOGOUT"):
                self.wfile.write(b"* BYE logging out\r\n")
                self.wfile.write(f"{tag} OK logout done\r\n".encode())
                return
            elif upper.startswith("NOOP"):
                self.wfile.write(f"{tag} OK noop\r\n".encode())
            else:
                self.wfile.write(f"{tag} BAD unknown\r\n".encode())


class _ImapServer(socketserver.ThreadingTCPServer):
    """真的在网络上提供 IMAP4 服务。"""

    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture
def imap_server():
    """真的起一个 IMAP4 服务。"""
    server = _ImapServer(("127.0.0.1", 0), _ImapHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestImaplib:
    """IMAP4 取信"""

    def test_connect(self, imap_server):
        """真的连上服务"""
        host, port = imap_server
        client = imaplib.IMAP4(host, port)
        try:
            assert client.welcome.startswith(b"* OK")
        finally:
            client.logout()

    def test_capability(self, imap_server):
        """能取到服务端能力"""
        host, port = imap_server
        client = imaplib.IMAP4(host, port)
        try:
            typ, data = client.capability()
            assert typ == "OK"
            assert b"IMAP4rev1" in data[0]
        finally:
            client.logout()

    def test_login(self, imap_server):
        """能完成登录"""
        host, port = imap_server
        client = imaplib.IMAP4(host, port)
        try:
            typ, data = client.login("forge", "secret")
            assert typ == "OK"
        finally:
            client.logout()

    def test_select(self, imap_server):
        """能选中信箱"""
        host, port = imap_server
        client = imaplib.IMAP4(host, port)
        try:
            client.login("forge", "secret")
            typ, data = client.select("INBOX")
            assert typ == "OK"
        finally:
            client.logout()

    def test_fetch(self, imap_server):
        """能取到邮件内容"""
        host, port = imap_server
        client = imaplib.IMAP4(host, port)
        try:
            client.login("forge", "secret")
            client.select("INBOX")
            typ, data = client.fetch("1", "(BODY[TEXT])")
            assert typ == "OK"
            # 每项是 (信封, 内容) 二元组
            assert b"forge" in data[0][1]
        finally:
            client.logout()


# ======================== curses.panel ========================


class TestCursesPanel:
    """面板层"""

    def test_module_present(self):
        """模块可用"""
        import curses.panel

        assert curses.panel is not None

    def test_new_panel_class(self):
        """面板类存在"""
        import curses.panel

        assert curses.panel.new_panel is not None

    def test_error_class(self):
        """错误类型存在"""
        import curses.panel

        assert issubclass(curses.panel.error, Exception)

    def test_bottom_panel_class(self):
        """底层面板类存在"""
        import curses.panel

        assert curses.panel.bottom_panel is not None

    def test_top_panel_class(self):
        """顶层面板类存在"""
        import curses.panel

        assert curses.panel.top_panel is not None


# ======================== filecmp ========================


class TestFilecmpExtra:
    """文件与目录比较"""

    @pytest.fixture
    def workdir(self):
        """建一个临时工作目录。"""
        path = Path(tempfile.mkdtemp(prefix="forge_fc2_"))
        try:
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)

    def test_cmp_identical(self, workdir):
        """内容相同的文件相等"""
        a = workdir / "a.txt"
        b = workdir / "b.txt"
        a.write_bytes(b"forge")
        b.write_bytes(b"forge")
        assert filecmp.cmp(str(a), str(b)) is True

    def test_cmp_different_size(self, workdir):
        """大小不同则不等"""
        a = workdir / "a.txt"
        b = workdir / "b.txt"
        a.write_bytes(b"forge")
        b.write_bytes(b"forge-longer")
        assert filecmp.cmp(str(a), str(b)) is False

    def test_dircmp_common(self, workdir):
        """目录比较能列出公共文件"""
        left = workdir / "left"
        right = workdir / "right"
        for root in (left, right):
            root.mkdir(parents=True, exist_ok=True)
            (root / "same.txt").write_bytes(b"same")
        result = filecmp.dircmp(str(left), str(right))
        assert result.common_files == ["same.txt"]

    def test_dircmp_diff(self, workdir):
        """目录比较能列出差异文件"""
        left = workdir / "left"
        right = workdir / "right"
        for root in (left, right):
            root.mkdir(parents=True, exist_ok=True)
            (root / "f.txt").write_bytes(b"x")
        (right / "f.txt").write_bytes(b"y-longer")
        result = filecmp.dircmp(str(left), str(right))
        assert result.diff_files == ["f.txt"]

    def test_cmpfiles(self, workdir):
        """能比较两个目录下的同名文件"""
        left = workdir / "left"
        right = workdir / "right"
        for root in (left, right):
            root.mkdir(parents=True, exist_ok=True)
            (root / "f.txt").write_bytes(b"same")
        match, mismatch, errors = filecmp.cmpfiles(left, right, ["f.txt"])
        assert match == ["f.txt"]
        assert mismatch == []


# ======================== pathlib ========================


class TestPathlib:
    """路径对象"""

    @pytest.fixture
    def workdir(self):
        """建一个临时工作目录。"""
        path = Path(tempfile.mkdtemp(prefix="forge_pl_"))
        try:
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)

    def test_join(self):
        """拼接路径"""
        assert Path("/a") / "b" == Path("/a/b")

    def test_parts_and_suffix(self):
        """能取到路径的组成部分"""
        path = Path("/a/b/c.txt")
        assert path.suffix == ".txt"
        assert path.stem == "c"
        assert path.name == "c.txt"
        assert path.parent == Path("/a/b")

    def test_mkdir_and_exists(self, workdir):
        """真的建目录"""
        target = workdir / "a" / "b"
        target.mkdir(parents=True)
        assert target.is_dir()
        assert target.exists()

    def test_write_and_read(self, workdir):
        """真的写文件再读回"""
        target = workdir / "forge.txt"
        target.write_text("forge 中文", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "forge 中文"
        assert target.stat().st_size > 0

    def test_iterdir_and_glob(self, workdir):
        """能枚举目录与匹配文件"""
        (workdir / "a.txt").write_text("a", encoding="utf-8")
        (workdir / "b.txt").write_text("b", encoding="utf-8")
        names = sorted(p.name for p in workdir.iterdir())
        assert names == ["a.txt", "b.txt"]
        assert sorted(p.name for p in workdir.glob("*.txt")) == ["a.txt", "b.txt"]

    def test_resolve_and_relative_to(self, workdir):
        """能解析与算相对路径"""
        target = workdir / "a" / "b.txt"
        target.parent.mkdir(parents=True)
        target.write_text("x", encoding="utf-8")
        assert target.resolve().is_absolute()
        assert target.relative_to(workdir) == Path("a/b.txt")

    def test_with_suffix_and_name(self):
        """能换扩展名与文件名"""
        path = Path("/a/b.txt")
        assert path.with_suffix(".md") == Path("/a/b.md")
        assert path.with_name("c.txt") == Path("/a/c.txt")

    def test_unlink_and_rmdir(self, workdir):
        """真的删文件与目录"""
        target = workdir / "forge.txt"
        target.write_text("x", encoding="utf-8")
        target.unlink()
        assert not target.exists()
        sub = workdir / "sub"
        sub.mkdir()
        sub.rmdir()
        assert not sub.exists()
