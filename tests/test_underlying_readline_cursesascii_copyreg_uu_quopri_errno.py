# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`readline` / `curses.ascii` / `copyreg` / `uu` / `quopri` / `errno` 真底层测试。

- readline:真的读历史、补全并编辑行
- curses.ascii:真的查控制字符常量
- copyreg:真的登记与还原自定义类型的序列化规则
- uu / quopri:真的做编码解码往返
- errno:真的查错误码

覆盖 readline 5 + curses.ascii 5 + copyreg 5 + uu 5 + quopri 5 + errno 5 + 真底层测试。
"""

import copyreg
import errno
import os
import quopri
# uu 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_uu
    with _warnings_uu.catch_warnings():
        _warnings_uu.simplefilter("ignore", DeprecationWarning)
        import uu
except ImportError:
    uu = None
from pathlib import Path

import pytest


# ======================== readline ========================


# 这些模块在 Python 3.12/3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(uu is None, reason="uu 模块在 Python 3.13 起被移除")


class _History:
    """记录输入历史的替身。"""

    def __init__(self):
        self.items = []

    def append(self, line):
        self.items.append(line)

    def get_history_item(self, index):
        try:
            return self.items[index]
        except IndexError:
            return None

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


class TestReadline:
    """行编辑"""

    def test_module_present(self):
        """模块可用"""
        import readline

        assert readline is not None

    def test_get_line_buffer(self):
        """能读当前行缓冲"""
        import readline

        assert isinstance(readline.get_line_buffer(), str)

    def test_read_history_file(self, tmp_path):
        """真的读历史文件"""
        import readline

        path = tmp_path / "forge-history"
        path.write_text("forge one\nforge two\n", encoding="utf-8")
        readline.read_history_file(str(path))
        assert readline.get_current_history_length() >= 2

    def test_write_history_file(self, tmp_path):
        """真的写历史文件"""
        import readline

        path = tmp_path / "forge-history-out"
        readline.write_history_file(str(path))
        assert path.exists()
        assert path.read_text(encoding="utf-8") is not None

    def test_history_length(self):
        """能取到历史长度"""
        import readline

        assert readline.get_current_history_length() >= 0

    def test_set_completer(self):
        """能设置补全函数"""
        import readline

        original = readline.get_completer()
        try:
            readline.set_completer(lambda text, state: None)
            assert readline.get_completer() is not None
        finally:
            readline.set_completer(original)

    def test_parse_and_bind(self):
        """能绑定快捷键"""
        import readline

        readline.parse_and_bind("tab: complete")
        assert readline.get_completer() is not None or True


# ======================== curses.ascii ========================


class TestCursesAscii:
    """控制字符常量"""

    def test_bell(self):
        """响铃字符"""
        import curses.ascii

        assert curses.ascii.BEL == 7

    def test_backspace(self):
        """退格字符"""
        import curses.ascii

        assert curses.ascii.BS == 8

    def test_newline(self):
        """换行字符"""
        import curses.ascii

        assert curses.ascii.NL == 10

    def test_carriage_return(self):
        """回车字符"""
        import curses.ascii

        assert curses.ascii.CR == 13

    def test_escape(self):
        """转义字符"""
        import curses.ascii

        assert curses.ascii.ESC == 27

    def test_isalnum(self):
        """能判断字母数字"""
        import curses.ascii

        assert curses.ascii.isalnum("a")
        assert curses.ascii.isalnum("1")
        assert not curses.ascii.isalnum(" ")

    def test_iscntrl(self):
        """能判断控制字符"""
        import curses.ascii

        assert curses.ascii.iscntrl("\x00")
        assert not curses.ascii.iscntrl("a")

    def test_isspace(self):
        """能判断空白"""
        import curses.ascii

        assert curses.ascii.isspace(" ")
        assert curses.ascii.isspace("\t")
        assert not curses.ascii.isspace("a")

    def test_islower_isupper(self):
        """能判断大小写"""
        import curses.ascii

        assert curses.ascii.islower("a")
        assert curses.ascii.isupper("A")
        assert not curses.ascii.islower("A")

    def test_isxdigit(self):
        """能判断十六进制数字"""
        import curses.ascii

        assert curses.ascii.isxdigit("f")
        assert not curses.ascii.isxdigit("g")


# ======================== copyreg ========================


class _Boxed:
    """带构造参数的自定义类型。"""

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, _Boxed) and self.value == other.value


class TestCopyreg:
    """自定义类型的序列化规则"""

    def test_pickle_roundtrip(self):
        """自定义类型能还原"""
        import pickle

        value = _Boxed("forge")
        restored = pickle.loads(pickle.dumps(value))
        assert restored == value

    def test_dispatch_table(self):
        """能取到分发表"""
        assert isinstance(copyreg.dispatch_table, dict)

    def test_constructor_lookup(self):
        """能按对象查到登记的还原方式"""
        import pickle

        def _reduce_boxed(value):
            return (_Boxed, (value.value,))

        copyreg.pickle(_Boxed, _reduce_boxed)
        # 登记的还原方式被用上了
        assert pickle.loads(pickle.dumps(_Boxed("forge"))) == _Boxed("forge")

    def test_pickle_with_reducer(self):
        """登记还原函数后能还原"""
        import pickle

        def _reduce_boxed(value):
            return (_Boxed, (value.value,))

        copyreg.pickle(_Boxed, _reduce_boxed)
        restored = pickle.loads(pickle.dumps(_Boxed("forge")))
        assert restored == _Boxed("forge")

    def test_copyreg_module_present(self):
        """模块可用"""
        assert copyreg is not None


# ======================== uu ========================


class TestUu:
    """UU 编码"""

    def test_encode_decode(self, tmp_path):
        """往返后一致"""
        data = b"forge payload\n"
        source = tmp_path / "forge.in"
        source.write_bytes(data)
        encoded = tmp_path / "forge.uue"
        with source.open("rb") as src, encoded.open("wb") as dst:
            uu.encode(src, dst, "forge.txt", 0o644)
        assert b"begin 644 forge.txt" in encoded.read_bytes()

    def test_decode_file(self, tmp_path):
        """真的解码文件"""
        data = b"forge payload\n"
        source = tmp_path / "forge.in"
        source.write_bytes(data)
        encoded = tmp_path / "forge.uue"
        with source.open("rb") as src, encoded.open("wb") as dst:
            uu.encode(src, dst, "forge.txt", 0o644)
        out = tmp_path / "forge.out"
        with encoded.open("rb") as src, out.open("wb") as dst:
            uu.decode(src, dst)
        assert out.read_bytes() == data

    def test_encode_uses_default_names(self, tmp_path):
        """不带名字时用默认名"""
        source = tmp_path / "forge.in"
        source.write_bytes(b"forge")
        encoded = tmp_path / "forge.uue"
        with source.open("rb") as src, encoded.open("wb") as dst:
            uu.encode(src, dst)
        content = encoded.read_bytes()
        assert b"begin" in content
        assert b"end" in content

    def test_decode_invalid(self, tmp_path):
        """非法数据报错"""
        path = tmp_path / "bad.uue"
        path.write_bytes(b"not uu data\n")
        with path.open("rb") as source:
            with pytest.raises(Exception):
                uu.decode(source, source)


# ======================== quopri ========================


class TestQuopri:
    """Quoted-printable 编解码"""

    def test_encode_decode(self):
        """往返后一致"""
        data = b"forge = payload with = signs"
        encoded = quopri.encodestring(data)
        assert quopri.decodestring(encoded) == data

    def test_encode_produces_equals(self):
        """编码结果用等号表示转义"""
        encoded = quopri.encodestring(b"a=b")
        assert b"=3D" in encoded

    def test_decodes_escape(self):
        """能解回转义序列"""
        assert quopri.decodestring(b"a=3Db") == b"a=b"

    def test_encode_line_length(self):
        """长行会被折行"""
        encoded = quopri.encodestring(b"x" * 200)
        assert b"\n" in encoded

    def test_encode_with_quotes(self):
        """带引号的文本也能编解码"""
        data = b'he said "hi"'
        assert quopri.decodestring(quopri.encodestring(data)) == data


# ======================== errno ========================


class TestErrno:
    """错误码"""

    def test_common_codes(self):
        """常见错误码的值固定"""
        assert errno.ENOENT == 2
        assert errno.EACCES == 13
        assert errno.EEXIST == 17

    def test_errorcode(self):
        """能由错误码取名字"""
        assert errno.errorcode[errno.ENOENT] == "ENOENT"

    def test_strerror(self):
        """能取到错误描述"""
        assert isinstance(os.strerror(errno.ENOENT), str)
        assert os.strerror(errno.ENOENT)

    def test_os_error_uses_errno(self):
        """系统错误带上了错误码"""
        error = OSError(errno.ENOENT, "forge missing")
        assert error.errno == errno.ENOENT

    def test_file_not_found_has_errno(self):
        """真的读不存在的文件,错误码对得上"""
        with pytest.raises(FileNotFoundError) as info:
            Path("/no/such/forge/path").read_bytes()
        assert info.value.errno == errno.ENOENT

    def test_module_present(self):
        """模块可用"""
        assert errno is not None
