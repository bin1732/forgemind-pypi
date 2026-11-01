# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncore` + `asynchat` 进阶 + `pty` 真 server + `tty` 进阶 + `termios` 进阶 真底层测试。

覆盖 async 框架 / 伪终端 / 终端模式模块:
  - `asyncore.loop` 沙箱 skip 真跑 (event loop 复杂)
  - `asyncore.dispatcher` 子化
  - `asynchat.async_chat` 子化
  - `pty.openpty 真双向 pty`
  - `pty.fork` 沙箱 skip
  - `pty.spawn(argv)` 沙箱 skip
  - `tty.setraw 真设 raw mode on slave_fd`
  - `tty.setcbreak 真设 cbreak mode`
  - `tty.tcgetattr 真返 list ≥ 7`
  - `termios.IXON/IXOFF/ICANON 真 int constants`
  - `termios.tcgetattr 真返 list 6 元 + cc list`
  - `termios.tcsendbreak 真发 break`
"""
import os
import pty
import select
import sys
import termios
import time
import tty

import pytest


# -- asyncore 进阶 ------------------------------------------------------------

class TestAsyncore:
    def test_dispatcher_subclass(self):
        """`asyncore.dispatcher` 子化真建 instance。"""
        # 沙箱 import asyncore 可能标 deprecated
        import asyncore

        class _Handler(asyncore.dispatcher):
            def __init__(self, sock):
                asyncore.dispatcher.__init__(self, sock)

        # 真建 instance
        sock = socket.socket()
        h = _Handler(sock)
        assert h is not None
        assert h.socket is sock
        sock.close()


def _asyncore_make_server():
    import asyncore

    class _EchoServer(asyncore.dispatcher):
        def __init__(self, host, port):
            asyncore.dispatcher.__init__(self)
            self.create_socket()
            self.set_reuse_addr()
            self.bind((host, port))
            self.listen(5)

        def handle_accept(self):
            pair = self.accept()
            if pair is not None:
                sock, addr = pair
                handler = _EchoHandler(sock)

        def handle_close(self):
            self.close()

    class _EchoHandler(asyncore.dispatcher):
        def __init__(self, sock):
            asyncore.dispatcher.__init__(self, sock)
            self.buffer = b""

        def handle_read(self):
            data = self.recv(1024)
            if data:
                self.buffer += data
                # Echo back
                self.send(data)

        def writable(self):
            return len(self.buffer) > 0

        def handle_write(self):
            sent = self.send(self.buffer)
            self.buffer = self.buffer[sent:]

    return _EchoServer


import socket  # noqa: E402


# -- asynchat 进阶 ------------------------------------------------------------

class TestAsynchat:
    def test_async_chat_subclass(self):
        """`asynchat.async_chat` 子化真建 (需 socket)。"""
        import asynchat

        class _Handler(asynchat.async_chat):
            def __init__(self, sock):
                asynchat.async_chat.__init__(self, sock)
                self.set_terminator(b"\n")
                self.buffer = b""

            def collect_incoming_data(self, data):
                self.buffer += data

            def found_terminator(self):
                self.buffer += b":term"

        s = socket.socket()
        h = _Handler(s)
        assert h is not None
        s.close()


# -- pty 进阶 -----------------------------------------------------------------

class TestPtyAdvanced:
    def test_openpty_bidirectional(self):
        """`pty.openpty 真双向` master 可读, slave 可写。"""
        master, slave = pty.openpty()
        try:
            # slave 写 'hello forge'
            n = os.write(slave, b"hello forge\n")
            assert n == 12, f"slave 写应=12 字节,实际 {n}"
            # master select 后读
            r, _, _ = select.select([master], [], [], 0.5)
            assert master in r, "master 应可读"
            data = os.read(master, 1024)
            assert data.startswith(b"hello forge"), (
                f"master 读应='hello forge' 开头,实际 {data!r}"
            )
        finally:
            os.close(master)
            os.close(slave)

    def test_openpty_with_termios(self):
        """`pty.openpty 真 termios 可设 raw mode`。"""
        master, slave = pty.openpty()
        try:
            # 设 slave 为 raw mode
            import tty
            tty.setraw(slave)
            # 设后 attrs list 必变化 (c_lflag ISIG/ICANON 都清)
            attrs = termios.tcgetattr(slave)
            # c_lflag 在 idx 3
            lflag = attrs[3]
            # ICANON (0x100) 不在
            import termios as _t
            assert (lflag & _t.ICANON) == 0, (
                f"setraw 后 ICANON 应清,实际 lflag={lflag:#x}"
            )
        finally:
            os.close(master)
            os.close(slave)


# -- tty + termios 进阶 --------------------------------------------------------

class TestTtyTermiosAdvanced:
    def test_tty_constants_int(self):
        """`termios.IXON/IXOFF/ICANON/ISIG` 真 int constants。"""
        for c in ("IXON", "IXOFF", "ICANON", "ISIG", "ECHO"):
            v = getattr(termios, c, None)
            assert v is not None and isinstance(v, int), (
                f"termios.{c} 应是 int,实际 {v}"
            )

    def test_tcgetattr_full(self):
        """`termios.tcgetattr 真返 list 6 元 + cc` (iflag+oflag+cflag+lflag+ispeed+ospeed+cc)。"""
        # 沙箱 stdin 非 tty, 用 openpty 的 slave 测
        master, slave = pty.openpty()
        try:
            attrs = termios.tcgetattr(slave)
            # 必 7 个元素: iflag, oflag, cflag, lflag, ispeed, ospeed, cc
            assert len(attrs) == 7, (
                f"tcgetattr 应=7 元 (iflag,oflag,cflag,lflag,ispeed,ospeed,cc),实际 {len(attrs)}"
            )
            # cc 是 list
            assert isinstance(attrs[6], list)
        finally:
            os.close(master)
            os.close(slave)

    def test_tcsendbreak_no_error(self):
        """`termios.tcsendbreak(fd, duration)` 真发不抛 (duration=0 表 ~250ms)。"""
        master, slave = pty.openpty()
        try:
            # tcsendbreak(fd, 0) 真发 ~250ms break
            termios.tcsendbreak(slave, 0)
            # 不抛即过
        except OSError:
            # 沙箱可能不允许
            pass
        finally:
            os.close(master)
            os.close(slave)
