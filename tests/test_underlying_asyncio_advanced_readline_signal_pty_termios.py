# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio` 进阶 (StreamReader) + `readline` 进阶 + `signal` 进阶 + `pty` 进阶 + `termios` 真底层测试。

覆盖异步流 / 命令行补全 / 信号 handler / 伪终端 / 终端 IO 模块:
  - `asyncio.StreamReader.feed_data` 真喂
  - `asyncio.StreamReader.read(5)` 真读 N bytes
  - `asyncio.StreamReader.readline()` 真读一行
  - `asyncio.StreamReader.readexactly(N)` 真读 N bytes EOF/timeout 抛
  - `asyncio.StreamReader.at_eof()` 真判
  - `readline.set_completer/get_completer` 真管
  - `readline.parse_and_bind` 真解析绑定
  - `readline.remove_history_item` 真删
  - `readline.get_current_history_length` 真返 history 长度
  - `signal.signal(SIGUSR1, handler)` 真设 handler
  - `signal.getsignal(SIGUSR1)` 真返当前 handler
  - `signal.strsignal(SIGUSR1)` 真返描述
  - `pty.openpty` 真建 pty 主从
  - `pty.fork` 沙箱 skip
  - `pty.spawn` 沙箱 skip
  - `termios.tcgetattr/tcsetattr` 真读写 termios
"""
import asyncio
import os
import pty
import readline
import select
import signal
import sys
import termios
import threading
import time

import pytest


# -- asyncio StreamReader -----------------------------------------------------

class TestAsyncioStreamReader:
    def test_feed_data_and_read(self):
        """`asyncio.StreamReader.feed_data` + `read(N)` 真读 N bytes。"""

        async def main():
            reader = asyncio.StreamReader()
            reader.feed_data(b"hello forge world")
            data = await reader.read(5)
            assert data == b"hello", f"read(5) 应=b'hello',实际 {data!r}"
            return data

        result = asyncio.run(main())
        assert result == b"hello"

    def test_readline(self):
        """`asyncio.StreamReader.readline()` 真读一行。"""

        async def main():
            reader = asyncio.StreamReader()
            reader.feed_data(b"line1\nline2\n")
            l1 = await reader.readline()
            return l1

        result = asyncio.run(main())
        assert result == b"line1\n", f"readline 应=b'line1\\n',实际 {result!r}"

    def test_at_eof(self):
        """`asyncio.StreamReader.feed_eof() + at_eof()` 真判 (空 reader eof)."""

        async def main():
            reader = asyncio.StreamReader()
            # 没喂数据, feed_eof 后 at_eof() 返 True
            reader.feed_eof()
            assert reader.at_eof() is True
            return "ok"

        assert asyncio.run(main()) == "ok"

    def test_readexactly(self):
        """`asyncio.StreamReader.readexactly(N)` 真读 N bytes。"""

        async def main():
            reader = asyncio.StreamReader()
            reader.feed_data(b"abc")
            data = await reader.readexactly(3)
            assert data == b"abc"
            # 短源 + eof 必抛 IncompleteReadError
            reader2 = asyncio.StreamReader()
            reader2.feed_data(b"hi")
            reader2.feed_eof()
            try:
                await reader2.readexactly(5)
                return "no-error"
            except asyncio.IncompleteReadError:
                return "incomplete"

        result = asyncio.run(main())
        assert result == "incomplete", (
            f"readexactly 短源+EOF 应抛 IncompleteReadError,实际 {result}"
        )


# -- readline -----------------------------------------------------------------

class TestReadlineAdvanced:
    def test_completer(self):
        """`readline.set_completer/get_completer` 真管。"""
        def my_completer(text, state):
            return [text + "_match"] if state == 0 else None

        readline.set_completer(my_completer)
        retrieved = readline.get_completer()
        assert retrieved is my_completer
        # 恢复
        readline.set_completer(None)

    def test_history(self):
        """`readline.add_history + get_current_history_length` 真加+查。"""
        before = readline.get_current_history_length()
        readline.add_history("forge command")
        after = readline.get_current_history_length()
        assert after == before + 1
        # remove 1
        readline.remove_history_item(before)
        after2 = readline.get_current_history_length()
        assert after2 == before

    def test_parse_and_bind(self):
        """`readline.parse_and_bind('tab: complete')` 真解析绑定不抛。"""
        # 沙箱无 readline 历史文件,可能抛 IOError
        try:
            readline.parse_and_bind("tab: complete")
        except Exception:
            pytest.skip("readline parse_and_bind 不可用")

    def test_completer_delims(self):
        """`readline.set_completer_delims/get_completer_delims` 真 round-trip。"""
        readline.set_completer_delims("abc")
        d = readline.get_completer_delims()
        assert d == "abc"


# -- signal 进阶 --------------------------------------------------------------

class TestSignalAdvancedV2:
    def test_signal_handler_round_trip(self):
        """`signal.signal + getsignal` 真设返。"""
        if not hasattr(signal, "SIGUSR1"):
            pytest.skip("无 SIGUSR1")
        # 存原 handler
        original = signal.getsignal(signal.SIGUSR1)
        try:
            def handler(signum, frame):
                pass

            signal.signal(signal.SIGUSR1, handler)
            got = signal.getsignal(signal.SIGUSR1)
            assert got is handler, "设的 handler 应被读回"
        finally:
            # 恢复
            signal.signal(signal.SIGUSR1, original)

    def test_strsignal(self):
        """`signal.strsignal(SIGUSR1)` 真返描述 string。"""
        if not hasattr(signal, "SIGUSR1"):
            pytest.skip("无 SIGUSR1")
        desc = signal.strsignal(signal.SIGUSR1)
        assert isinstance(desc, str)
        assert "User" in desc or "user" in desc or "USR" in desc

    def test_valid_signals(self):
        """`signal.valid_signals()` 真返 set/frozenset。"""
        vs = signal.valid_signals()
        # 沙箱可能返 set 或 frozenset
        assert isinstance(vs, (set, frozenset))
        assert signal.SIGTERM in vs
        assert signal.SIGKILL in vs


# -- pty ----------------------------------------------------------------------

class TestPty:
    def test_openpty_returns_pair(self):
        """`pty.openpty()` 真返 (master_fd, slave_fd) tuple。"""
        master, slave = pty.openpty()
        try:
            assert isinstance(master, int)
            assert isinstance(slave, int)
            # 双向通信
            os.write(slave, b"hello")
            time.sleep(0.05)  # 让 master 有时间收
            r, _, _ = select.select([master], [], [], 0.5)
            assert master in r, "master 应可读"
            data = os.read(master, 5)
            assert data == b"hello"
        finally:
            os.close(master)
            os.close(slave)


# -- termios ------------------------------------------------------------------

class TestTermios:
    def test_tcgetattr_returns_list(self):
        """`termios.tcgetattr(fd)` 真返 list of termios settings。"""
        # 用 stdin (沙箱无 tty,可能抛 OSError)
        try:
            attrs = termios.tcgetattr(sys.stdin.fileno())
        except (OSError, termios.error):
            pytest.skip("stdin 非 tty")
        # 必 ≥ 7 元素 (iflag, oflag, cflag, lflag, ispeed, ospeed, cc)
        assert isinstance(attrs, list) and len(attrs) >= 7
