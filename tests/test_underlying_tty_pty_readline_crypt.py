# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tty` + `pty` + `readline` + `crypt` 真底层测试。

覆盖 POSIX 终端支撑模块:
  - `tty.setraw` + `tty.setcbreak` 真把 stdin 切到 raw/cbreak 模式
    并恢复原 settings
  - `pty.openpty` 真开 master/slave fd 对,slave 上 `os.write(b"hi")`
    在 master 端 `os.read` 出来
  - `readline.parse_and_bind` + `readline.get_line_buffer` 真改
    GNU readline 绑定并查回 buffer
  - `crypt.crypt("password", salt)` 真用 DES 哈希,头 2 字符 = salt
"""
# crypt 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import crypt
except ImportError:
    crypt = None
import os
import pty
import pytest
import readline
import select
import sys
import termios
import tty

import pytest


# -- tty ----------------------------------------------------------------------

# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(crypt is None, reason="crypt 模块在 Python 3.13 起被移除")


class TestTty:
    def test_setraw_and_restore_stdin(self):
        """`tty.setraw` 真把 stdin 切到 raw 模式,termios 标志位变化。

        调用前 `lflag` 含 `ICANON`,调用后不再含 `ICANON`。
        `tty.setcbreak` 同样去掉 `ICANON`。
        最后恢复原 mode,确认 round-trip。
        """
        if not sys.stdin.isatty():
            pytest.skip("stdin 非 tty,跳过")
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            after_raw = termios.tcgetattr(fd)
            assert (after_raw[3] & termios.ICANON) == 0, (
                "setraw 后 lflag 应清 ICANON 位"
            )
            tty.setcbreak(fd)
            after_cb = termios.tcgetattr(fd)
            assert (after_cb[3] & termios.ICANON) == 0, (
                "setcbreak 后 lflag 也应清 ICANON 位"
            )
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        # 恢复后回到原 ICANON 状态
        restored = termios.tcgetattr(fd)
        assert (restored[3] & termios.ICANON) == (old[3] & termios.ICANON)

    def test_tty_setcbreak_differs_from_setraw(self):
        """`tty.setraw` 与 `tty.setcbreak` 行为不同:前者连 ECHO/ISIG 也清。"""
        if not sys.stdin.isatty():
            pytest.skip("stdin 非 tty,跳过")
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            raw_lflag = termios.tcgetattr(fd)[3]
            tty.setcbreak(fd)
            cb_lflag = termios.tcgetattr(fd)[3]
            # setraw 应该清掉 ISIG 位;setcbreak 不应清
            assert (raw_lflag & termios.ISIG) == 0, "setraw 应清 ISIG"
            assert (cb_lflag & termios.ISIG) != 0, "setcbreak 应保留 ISIG"
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# -- pty ----------------------------------------------------------------------

class TestPty:
    def test_openpty_round_trip(self):
        """`pty.openpty` 真开 master/slave,从 slave 写 master 读。

        master, slave = pty.openpty();
        os.write(slave, b"hi") -> master 端 select + os.read 拿回 b"hi"。
        """
        master, slave = pty.openpty()
        try:
            os.write(slave, b"hi")
            # 等待数据可用
            rlist, _, _ = select.select([master], [], [], 1.0)
            assert rlist, "1s 内 master 仍不可读"
            data = os.read(master, 16)
            assert data == b"hi", f"应读回 b'hi',实际 {data!r}"
        finally:
            os.close(master)
            os.close(slave)


# -- readline -----------------------------------------------------------------

class TestReadline:
    def test_parse_and_bind_then_set_completer_delims(self):
        """`readline.parse_and_bind` 不抛异常 + 随后修改 completer delims。

        解析一条无害绑定 (e.g. `Control-l: clear-screen`),不抛;
        然后 `set_completer_delims` + `get_completer_delims` 验证写入生效。
        """
        readline.parse_and_bind("Control-l: clear-screen")
        readline.set_completer_delims(" \t\n;")
        delims = readline.get_completer_delims()
        assert delims == " \t\n;", (
            f"completer delims 应为 ' \\t\\n;',实际 {delims!r}"
        )

    def test_set_completer_round_trip(self):
        """`readline.set_completer` 存函数,`readline.get_completer` 拿回。"""
        def my_complete(text, state):
            return text + str(state) if state < 2 else None

        readline.set_completer(my_complete)
        got = readline.get_completer()
        assert got is my_complete, f"应拿回 my_complete,实际 {got!r}"

    def test_add_history_and_get_history_item(self):
        """`readline.add_history` + `get_history_item` 真按 1-based 索引返回。"""
        # 先清空
        readline.clear_history()
        readline.add_history("forge alpha")
        readline.add_history("forge beta")
        n = readline.get_current_history_length()
        assert n == 2, f"history 应有 2 条,实际 {n}"
        assert readline.get_history_item(1) == "forge alpha"
        assert readline.get_history_item(2) == "forge beta"


# -- crypt --------------------------------------------------------------------

class TestCrypt:
    def test_crypt_returns_string_starting_with_salt(self):
        """`crypt.crypt('password', salt)` 真 DES 哈希,头 2 字符等于 salt。"""
        hashed = crypt.crypt("hello", "ab")
        assert isinstance(hashed, str)
        assert hashed.startswith("ab"), (
            f"crypt 输出前 2 字符应等于 salt 'ab',实际 {hashed[:4]!r}"
        )
        # 13 字符是 DES crypt 输出长度
        assert len(hashed) >= 13, (
            f"DES crypt 输出 ≥ 13 字符,实际 len={len(hashed)}"
        )

    def test_crypt_is_deterministic(self):
        """同 password + salt 两次调用返相同结果。"""
        a = crypt.crypt("forge", "xy")
        b = crypt.crypt("forge", "xy")
        assert a == b, f"同 input 应返相同结果,实际 {a!r} vs {b!r}"

    def test_crypt_different_salt_gives_different_hash(self):
        """不同 salt 应得不同 hash。"""
        a = crypt.crypt("forge", "ab")
        b = crypt.crypt("forge", "cd")
        assert a != b, "不同 salt 应得不同 hash"
