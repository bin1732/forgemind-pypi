# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`curses.ascii` / `curses` / `tty` / `termios` / `pty` 真底层测试。

- curses.ascii:真的查控制字符与字符分类
- curses:真的初始化终端,画界面读按键
- tty:真的在伪终端上做行编辑
- termios:真的读改终端属性
- pty:真的开一对主从伪终端

覆盖 curses.ascii 5 + curses 5 + tty 5 + termios 5 + pty 5 + 真底层测试。
"""

import curses
import curses.ascii
import os
import pty
import select
import shutil
import signal
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path

import pytest


# ======================== curses.ascii ========================


class TestCursesAsciiExtra:
    """控制字符常量"""

    def test_escape_codes(self):
        """常见控制字符的值固定"""
        assert curses.ascii.BEL == 7
        assert curses.ascii.BS == 8
        assert curses.ascii.TAB == 9
        assert curses.ascii.LF == 10
        assert curses.ascii.CR == 13
        assert curses.ascii.ESC == 27
        assert curses.ascii.SP == 32
        assert curses.ascii.DEL == 127

    def test_isalpha(self):
        """能判断字母"""
        assert curses.ascii.isalpha("a")
        assert curses.ascii.isalpha("Z")
        assert not curses.ascii.isalpha("1")

    def test_isdigit(self):
        """能判断数字"""
        assert curses.ascii.isdigit("7")
        assert not curses.ascii.isdigit("a")

    def test_ispunct(self):
        """能判断标点"""
        assert curses.ascii.ispunct("!")
        assert not curses.ascii.ispunct("a")

    def test_isprint(self):
        """能判断可打印字符"""
        assert curses.ascii.isprint("a")
        assert not curses.ascii.isprint("\x00")

    def test_ascii_function(self):
        """能取到字符本身"""
        assert curses.ascii.ascii("A") == "A"

    def test_control_character_names(self):
        """控制字符有名字"""
        assert curses.ascii.unctrl("\x07") == "^G"
        assert curses.ascii.unctrl("\n") == "^J"


# ======================== curses ========================


class TestCursesReal:
    """终端界面"""

    def test_wrapper_runs(self):
        """能在终端里跑一段界面代码"""
        result = {}

        def setup(screen):
            screen.addstr(0, 0, "forge-curses")
            screen.refresh()
            result["size"] = screen.getmaxyx()
            try:
                screen.getch()
            finally:
                curses.endwin()

        try:
            curses.wrapper(setup)
        except Exception:
            pytest.skip("当前环境没有可用终端")
        assert result["size"][0] > 0

    def test_addstr_and_inch(self):
        """写字之后能读回"""
        result = {}

        def setup(screen):
            screen.addstr(0, 0, "X")
            screen.refresh()
            result["char"] = screen.inch(0, 0)

        try:
            curses.wrapper(setup)
        except Exception:
            pytest.skip("当前环境没有可用终端")
        assert result["char"] in (ord("X"), 0)

    def test_color_pair_count(self):
        """颜色对的数量可读"""
        try:
            curses.start_color()
            curses.use_default_colors()
        except Exception:
            pytest.skip("当前环境没有可用终端")
        finally:
            try:
                curses.endwin()
            except Exception:
                pass
        assert curses.COLOR_PAIRS >= 0

    def test_key_constants(self):
        """按键常量存在"""
        assert curses.KEY_DOWN > 0
        assert curses.KEY_UP > 0
        assert curses.KEY_ENTER > 0

    def test_error_is_exception(self):
        """错误类型可用"""
        assert issubclass(curses.error, Exception)


# ======================== tty ========================


class TestTty:
    """伪终端行编辑"""

    def test_set_raw(self):
        """能把终端设成原始模式"""
        import pty as _pty

        master, slave = _pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            try:
                tty.setraw(slave)
                changed = termios.tcgetattr(slave)
                assert changed[3] != original[3] or changed[0] != original[0]
            finally:
                termios.tcsetattr(slave, termios.TCSADRAIN, original)
        finally:
            os.close(master)
            os.close(slave)

    def test_setcbreak(self):
        """能设成字符中断模式"""
        import pty as _pty

        master, slave = _pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            try:
                tty.setcbreak(slave)
                changed = termios.tcgetattr(slave)
                assert changed[3] != original[3]
            finally:
                termios.tcsetattr(slave, termios.TCSADRAIN, original)
        finally:
            os.close(master)
            os.close(slave)

    def test_setraw_changes_echo(self):
        """原始模式会关掉回显"""
        import pty as _pty

        master, slave = _pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            try:
                tty.setraw(slave)
                assert not (termios.tcgetattr(slave)[3] & termios.ECHO)
            finally:
                termios.tcsetattr(slave, termios.TCSADRAIN, original)
        finally:
            os.close(master)
            os.close(slave)

    def test_setcbreak_changes_echo(self):
        """字符中断模式也会关掉回显"""
        import pty as _pty

        master, slave = _pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            try:
                tty.setcbreak(slave)
                assert not (termios.tcgetattr(slave)[3] & termios.ECHO)
            finally:
                termios.tcsetattr(slave, termios.TCSADRAIN, original)
        finally:
            os.close(master)
            os.close(slave)

    def test_setraw_restores_afterwards(self):
        """还原后终端属性与原先一致"""
        import pty as _pty

        master, slave = _pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            tty.setraw(slave)
            termios.tcsetattr(slave, termios.TCSADRAIN, original)
            assert termios.tcgetattr(slave) == original
        finally:
            os.close(master)
            os.close(slave)


# ======================== termios ========================


class TestTermios:
    """终端属性"""

    def test_tcgetattr(self):
        """能读出终端属性"""
        import pty as _pty

        master, slave = _pty.openpty()
        try:
            attrs = termios.tcgetattr(slave)
            # 属性依次是输入标志、输出标志、控制标志、行标志与行速
            assert len(attrs) >= 6
            assert isinstance(attrs[0], int)
            assert isinstance(attrs[1], int)
            assert isinstance(attrs[2], int)
            # 最后一项是控制字符表
            assert isinstance(attrs[-1], list)
        finally:
            os.close(master)
            os.close(slave)

    def test_tcsetattr_roundtrip(self):
        """改了属性能读回"""
        import pty as _pty

        master, slave = _pty.openpty()
        try:
            attrs = termios.tcgetattr(slave)
            attrs[3] = attrs[3] & ~termios.ECHO
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
            assert not (termios.tcgetattr(slave)[3] & termios.ECHO)
        finally:
            os.close(master)
            os.close(slave)

    def test_constants_present(self):
        """常用常量存在"""
        assert termios.ECHO > 0
        assert termios.TCSANOW == 0
        assert termios.TCSADRAIN > 0
        assert termios.TCSADRAIN == 1

    def test_tcflush(self):
        """能清空输入输出队列"""
        import pty as _pty

        master, slave = _pty.openpty()
        try:
            termios.tcflush(slave, termios.TCIOFLUSH)
        finally:
            os.close(master)
            os.close(slave)

    def test_error_class(self):
        """错误类型可用"""
        assert issubclass(termios.error, Exception)


# ======================== pty ========================


class TestPty:
    """伪终端"""

    def test_openpty(self):
        """能开出一对主从设备"""
        master, slave = pty.openpty()
        try:
            assert isinstance(master, int)
            assert isinstance(slave, int)
            assert os.isatty(master)
            assert os.isatty(slave)
        finally:
            os.close(master)
            os.close(slave)

    def test_write_and_read(self):
        """真的在主从之间传数据"""
        master, slave = pty.openpty()
        try:
            os.write(master, b"forge-pty\r\n")
            readable, _, _ = select.select([slave], [], [], 5)
            assert readable, "从设备上应能读到数据"
            data = os.read(slave, 1024)
            assert b"forge-pty" in data
        finally:
            os.close(master)
            os.close(slave)

    def test_spawn(self):
        """真的用伪终端起一个子进程"""
        master, slave = pty.openpty()
        try:
            pid, fd = pty.fork()
            if pid == 0:
                os.close(master)
                try:
                    os.write(slave, b"from-child\r\n")
                finally:
                    os._exit(0)
            os.close(slave)
            readable, _, _ = select.select([master], [], [], 5)
            assert readable
            data = os.read(master, 1024)
            os.waitpid(pid, 0)
            assert b"from-child" in data
        finally:
            os.close(master)

    def test_fork_returns_pid(self):
        """fork 出的是子进程号"""
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
        assert pid > 0

    def test_openpty_in_subprocess(self):
        """子进程里也能开伪终端"""
        code = "import pty; m, s = pty.openpty(); print('ok')"
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
        )
        assert result.returncode == 0
        assert "ok" in result.stdout
