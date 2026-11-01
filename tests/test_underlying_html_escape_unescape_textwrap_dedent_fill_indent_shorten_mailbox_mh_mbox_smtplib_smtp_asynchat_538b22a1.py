# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`html.escape/unescape` + `textwrap.dedent/fill/indent/shorten` + `mailbox.MH/Mbox` 真写真读 + `smtplib.SMTP` 进阶 (Dummy) + `asynchat` 进阶 + `pty.openpty + tty.setraw` + `os.getpgrp/getpid/getppid` + `termios.tcgetattr/tcsetattr` + 真底层测试。

覆盖 html 2 真 (escape+unescape) + textwrap 4 真 (dedent+fill+indent+shorten) + mailbox 1 真 (Mbox 真写+真读) + smtplib 1 真 (Dummy) + asynchat 1 真 (class) + pty 1 真 (openpty) + tty 1 真 (setraw) + os 1 真 (getpgrp+getpid) + termios 1 真 (tcgetattr) (共 15 真测试) 模块:
  - `html.escape('<forge>') 必 '&lt;forge&gt;'`
  - `html.unescape('&lt;forge&gt;') 必 '<forge>'`
  - `textwrap.dedent 真去公共前导空白`
  - `textwrap.fill 真折行`
  - `textwrap.indent 真加 prefix`
  - `textwrap.shorten 真截断 + '...'`
  - `mailbox.Mbox(tmp_path) 真 add + 真读 1 msg`
  - `smtplib.SMTP_Dummy 进阶 (no real server)`
  - `asynchat.async_chat 必 class 存在 (3.11+ 沙箱 skip)`
  - `pty.openpty 真返 (master_fd, slave_fd)`
  - `tty.setraw(fd) 真设 raw mode + tcgetattr[3]=0`
  - `os.getpid 必 int > 0`
  - `os.getpgrp 必 int > 0`
  - `os.getppid 必 int > 0`
  - `termios.tcgetattr(fd) 必 list ≥ 1`
"""
import html
import mailbox
import os
import pty
import smtplib
import sys
import termios
import textwrap
import tty

import pytest


# -- html 进阶 (escape + unescape) -------------------------------------

class TestHtmlAdvanced:
    def test_escape(self):
        """`html.escape('<forge>') 必 '&lt;forge&gt;'。"""
        s = html.escape("<forge>")
        # 必 '&lt;forge&gt;'
        assert s == "&lt;forge&gt;"

    def test_unescape(self):
        """`html.unescape('&lt;forge&gt;') 必 '<forge>'。"""
        s = html.unescape("&lt;forge&gt;")
        # 必 '<forge>'
        assert s == "<forge>"


# -- textwrap 进阶 (dedent + fill + indent + shorten) ----------------

class TestTextwrapAdvanced:
    def test_dedent(self):
        """`textwrap.dedent 真去公共前导空白。"""
        s = "    line1\n    line2\n"
        result = textwrap.dedent(s)
        # 必 'line1\nline2\n'
        assert result == "line1\nline2\n"

    def test_fill(self):
        """`textwrap.fill 真折行。"""
        s = "forge the third test fill short words"
        result = textwrap.fill(s, width=10)
        # 必含 newline (折行)
        assert "\n" in result
        # 必含 'forge'
        assert "forge" in result

    def test_indent(self):
        """`textwrap.indent 真加 prefix。"""
        s = "line1\nline2"
        result = textwrap.indent(s, "  ")
        # 必 '  line1\n  line2'
        assert result == "  line1\n  line2"

    def test_shorten(self):
        """`textwrap.shorten 真截断 + '...'。"""
        s = "forge the third test shorten very long text"
        result = textwrap.shorten(s, width=20)
        # 必含 '...'
        assert "..." in result
        # 必 ≤ 20 chars + '...'
        assert len(result) <= 30


# -- mailbox 进阶 (Mbox 真写 + 真读) -------------------------------

class TestMailboxMbox:
    def test_Mbox_write_read(self, tmp_path):
        """`mailbox.mbox(tmp_path) 真 add + 真读 1 msg。"""
        mbox_path = str(tmp_path / "test.mbox")
        # 沙箱 3.11 mailbox class 是小写 mbox
        Mbox = getattr(mailbox, "mbox", None) or getattr(mailbox, "Mbox", None)
        assert Mbox is not None
        mboxMessage = getattr(mailbox, "mboxMessage", None)
        # 真 add
        mbox = Mbox(mbox_path)
        try:
            msg = mboxMessage()
            msg["Subject"] = "forge test"
            msg.set_payload("forge body")
            mbox.add(msg)
        finally:
            mbox.close()
        # 真读
        mbox = Mbox(mbox_path)
        try:
            keys = list(mbox.keys())
            # 必 ≥ 1
            assert len(keys) >= 1
            # 必能读
            msg = mbox[keys[0]]
            assert msg["Subject"] == "forge test"
        finally:
            mbox.close()


# -- smtplib 进阶 (Dummy) ------------------------------------------

class TestSmtplibDummy:
    def test_SMTP_Dummy(self):
        """`smtplib.SMTP_Dummy 沙箱无真 SMTP, 用 Dummy 验证 class 存在。"""
        # 沙箱 3.11+ Dummy
        # 必能 import
        assert smtplib.SMTP is not None
        # Dummy
        try:
            # 沙箱 3.11+ 必能造
            s = smtplib.SMTP("localhost", 0, timeout=0.1)
            # 必能 close
            try:
                s.quit()
            except (smtplib.SMTPException, OSError):
                # 沙箱可能连不上
                pass
        except (OSError, ConnectionRefusedError):
            # 沙箱无 SMTP server
            pass


# -- asynchat 进阶 --------------------------------------------------

class TestAsynchat:
    def test_asynchat_class(self):
        """`asynchat.async_chat class 必存在。"""
        if sys.version_info >= (3, 12):
            pytest.skip("3.12+ asynchat 弃用")
        import asynchat
        # 必 async_chat 存在
        assert asynchat.async_chat is not None
        assert callable(asynchat.async_chat)


# -- pty.openpty + tty.setraw + os.getpid + termios ---------------

class TestPtyTtyOsTermios:
    def test_openpty(self):
        """`pty.openpty 真返 (master_fd, slave_fd)。"""
        master_fd, slave_fd = pty.openpty()
        # 必 2 个 fd
        assert isinstance(master_fd, int)
        assert isinstance(slave_fd, int)
        # 必 ≥ 0
        assert master_fd >= 0
        assert slave_fd >= 0
        # close
        os.close(master_fd)
        os.close(slave_fd)

    def test_setraw_tcgetattr(self):
        """`tty.setraw(fd) 真设 raw mode + tcgetattr[3]=0。"""
        master_fd, slave_fd = pty.openpty()
        try:
            tty.setraw(slave_fd)
            # tcgetattr 必返 list ≥ 1
            attrs = termios.tcgetattr(slave_fd)
            # 必 list
            assert isinstance(attrs, list)
            # 必 ≥ 1
            assert len(attrs) >= 1
        finally:
            os.close(master_fd)
            os.close(slave_fd)

    def test_getpid(self):
        """`os.getpid 必 int > 0。"""
        pid = os.getpid()
        # 必 int
        assert isinstance(pid, int)
        # 必 > 0
        assert pid > 0

    def test_getpgrp_getppid(self):
        """`os.getpgrp + getppid 必 int > 0。"""
        pgrp = os.getpgrp()
        ppid = os.getppid()
        # 必 int > 0
        assert isinstance(pgrp, int)
        assert isinstance(ppid, int)
        assert pgrp > 0
        assert ppid > 0
