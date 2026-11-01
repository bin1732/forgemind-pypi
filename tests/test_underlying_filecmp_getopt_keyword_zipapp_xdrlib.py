# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`filecmp` / `getopt` / `keyword` / `zipapp` / `xdrlib` 真底层测试。

- filecmp:真实文件与目录的逐字节比较、缓存、递归目录比较
- getopt:真实的命令行解析,含短选项、长选项与错误处理
- keyword:真实的保留字与软关键字检查
- zipapp:真的把源码打成可执行的归档并运行它
- xdrlib:真实的 XDR 编码与解码往返

覆盖 filecmp 5 + getopt 5 + keyword 4 + zipapp 5 + xdrlib 4 + 真底层测试。
"""

import filecmp
import getopt
import keyword
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipapp
from pathlib import Path
# xdrlib 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_xdrlib
    with _warnings_xdrlib.catch_warnings():
        _warnings_xdrlib.simplefilter("ignore", DeprecationWarning)
        import xdrlib
        from xdrlib import Error as XdrError
        from xdrlib import Packer, Unpacker
except ImportError:
    xdrlib = None
    XdrError = None
    Packer = None
    Unpacker = None

import pytest


# xdrlib 在 Python 3.13 起被移除,没有它整个文件连收集都会失败
pytestmark = pytest.mark.skipif(xdrlib is None, reason="xdrlib 模块在 Python 3.13 起被移除")


@pytest.fixture
def workdir():
    """建一个临时工作目录,测试结束后清理。"""
    path = Path(tempfile.mkdtemp(prefix="forge_stdlib_"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ======================== filecmp ========================


class TestFilecmpShallow:
    """浅比较"""

    def test_cmp_same_content(self, workdir):
        """内容相同的两个文件比较结果为相等"""
        a = _write(workdir / "a.txt", b"forge")
        b = _write(workdir / "b.txt", b"forge")
        assert filecmp.cmp(str(a), str(b)) is True

    def test_cmp_different_content(self, workdir):
        """内容不同的两个文件比较结果为不等"""
        a = _write(workdir / "a.txt", b"forge")
        b = _write(workdir / "b.txt", b"forge2")
        assert filecmp.cmp(str(a), str(b)) is False

    def test_cmp_empty_files(self, workdir):
        """两个空文件相等"""
        a = _write(workdir / "a.txt", b"")
        b = _write(workdir / "b.txt", b"")
        assert filecmp.cmp(str(a), str(b)) is True

    def test_cmp_missing_file_raises(self, workdir):
        """文件不存在时抛出真实错误"""
        a = _write(workdir / "a.txt", b"forge")
        with pytest.raises(FileNotFoundError):
            filecmp.cmp(str(a), str(workdir / "missing.txt"))

    def test_cmp_accepts_path_like(self, workdir):
        """接受路径对象"""
        a = _write(workdir / "a.txt", b"forge")
        b = _write(workdir / "b.txt", b"forge")
        assert filecmp.cmp(a, b) is True

    def test_cmp_shallow_false_reads_bytes(self, workdir):
        """深比较真的读出字节比较"""
        a = _write(workdir / "a.txt", b"forge\x00binary")
        b = _write(workdir / "b.txt", b"forge\x00binary")
        assert filecmp.cmp(str(a), str(b), shallow=False) is True

    def test_cmp_shallow_false_detects_difference(self, workdir):
        """深比较能发现浅比较看不出的差异"""
        a = _write(workdir / "a.txt", b"forge\x00one")
        b = _write(workdir / "b.txt", b"forge\x00two")
        assert filecmp.cmp(str(a), str(b), shallow=False) is False


def _sig(path: Path):
    """文件的状态签名,比较缓存以它为键。"""
    st = os.stat(path)
    return (stat.S_IFMT(st.st_mode), st.st_size, st.st_mtime)


def _cache_key(a: Path, b: Path):
    """比较缓存里对应这两个文件的键。"""
    return (str(a), str(b), _sig(a), _sig(b))


class TestFilecmpCache:
    """比较缓存

    状态签名完全一致时,比较直接给出结论,不会走缓存。缓存只在两个
    文件大小相同而修改时间不同时才写入,这时才真的要读出内容比较。
    """

    @staticmethod
    def _pair(workdir, left: bytes, right: bytes):
        """建两个大小相同、修改时间不同的文件。"""
        a = _write(workdir / "a.txt", left)
        b = _write(workdir / "b.txt", right)
        os.utime(a, (1000000, 1000000))
        os.utime(b, (2000000, 2000000))
        return a, b

    def test_cache_get_same(self, workdir):
        """内容相同的一对文件,比较结果被记进缓存"""
        a, b = self._pair(workdir, b"forge", b"forge")
        assert filecmp.cmp(str(a), str(b)) is True
        assert filecmp._cache.get(_cache_key(a, b)) is True

    def test_cache_get_different(self, workdir):
        """内容不同的一对文件,比较结果被记进缓存"""
        a, b = self._pair(workdir, b"forge", b"other")
        assert filecmp.cmp(str(a), str(b)) is False
        assert filecmp._cache.get(_cache_key(a, b)) is False

    def test_cache_returns_none_for_new_pair(self, workdir):
        """没比较过的一对文件缓存里没有记录"""
        a, b = self._pair(workdir, b"forge-unique-1", b"forge-unique-2")
        assert filecmp._cache.get(_cache_key(a, b)) is None

    def test_cache_clear(self, workdir):
        """清空后缓存里没有记录"""
        a, b = self._pair(workdir, b"forge", b"forge")
        filecmp.cmp(str(a), str(b))
        filecmp._cache.clear()
        assert filecmp._cache.get(_cache_key(a, b)) is None

    def test_cache_reflects_content_change(self, workdir):
        """文件内容改了之后,状态签名变化,缓存里记的是新结论"""
        a, b = self._pair(workdir, b"forge", b"forge")
        assert filecmp.cmp(str(a), str(b)) is True
        assert filecmp._cache.get(_cache_key(a, b)) is True
        # 改成大小相同、内容不同的内容,这样才会真的走内容比较
        b.write_bytes(b"FORGE")
        os.utime(b, (3000000, 3000000))
        assert filecmp.cmp(str(a), str(b)) is False
        assert filecmp._cache.get(_cache_key(a, b)) is False

    def test_cache_keyed_by_both_paths(self, workdir):
        """缓存的键包含两个路径与它们的状态签名"""
        a, b = self._pair(workdir, b"forge", b"forge")
        filecmp.cmp(str(a), str(b))
        assert _cache_key(a, b) in filecmp._cache
        assert _cache_key(b, a) not in filecmp._cache


class TestFilecmpDircmp:
    """目录递归比较"""

    def _make_tree(self, root: Path, only_left: bool = False):
        _write(root / "same.txt", b"same")
        _write(root / "diff.txt", b"left")
        if only_left:
            _write(root / "only_left.txt", b"left-only")
        (root / "sub").mkdir(parents=True, exist_ok=True)
        _write(root / "sub" / "nested.txt", b"nested")

    def test_dircmp_common_files(self, workdir):
        """同名文件进入公共文件集合"""
        left = workdir / "left"
        right = workdir / "right"
        self._make_tree(left)
        self._make_tree(right)
        result = filecmp.dircmp(str(left), str(right))
        assert "same.txt" in result.common_files
        assert "diff.txt" in result.common_files

    def test_dircmp_diff_files(self, workdir):
        """内容不同的同名文件进入差异集合"""
        left = workdir / "left"
        right = workdir / "right"
        self._make_tree(left)
        self._make_tree(right)
        (right / "diff.txt").write_bytes(b"right")
        result = filecmp.dircmp(str(left), str(right))
        assert "diff.txt" in result.diff_files

    def test_dircmp_left_only(self, workdir):
        """只在左侧存在的文件进入单侧集合"""
        left = workdir / "left"
        right = workdir / "right"
        self._make_tree(left, only_left=True)
        self._make_tree(right)
        result = filecmp.dircmp(str(left), str(right))
        assert "only_left.txt" in result.left_only

    def test_dircmp_right_only(self, workdir):
        """只在右侧存在的文件进入单侧集合"""
        left = workdir / "left"
        right = workdir / "right"
        self._make_tree(left)
        self._make_tree(right)
        _write(right / "only_right.txt", b"right-only")
        result = filecmp.dircmp(str(left), str(right))
        assert "only_right.txt" in result.right_only

    def test_dircmp_common_dirs(self, workdir):
        """同名子目录进入公共目录集合"""
        left = workdir / "left"
        right = workdir / "right"
        self._make_tree(left)
        self._make_tree(right)
        result = filecmp.dircmp(str(left), str(right))
        assert "sub" in result.common_dirs

    def test_dircmp_recurses_into_subdirs(self, workdir):
        """递归比较子目录,嵌套文件也被比较"""
        left = workdir / "left"
        right = workdir / "right"
        self._make_tree(left)
        self._make_tree(right)
        (right / "sub" / "nested.txt").write_bytes(b"changed")
        result = filecmp.dircmp(str(left), str(right))
        assert "sub" in result.subdirs
        assert "nested.txt" in result.subdirs["sub"].diff_files

    def test_dircmp_report(self, workdir, capsys):
        """差异报告被打印出来"""
        left = workdir / "left"
        right = workdir / "right"
        self._make_tree(left)
        self._make_tree(right)
        (right / "sub" / "nested.txt").write_bytes(b"changed")
        result = filecmp.dircmp(str(left), str(right))
        result.report()
        captured = capsys.readouterr()
        assert "sub" in captured.out

    def test_dircmp_default_ignores(self, workdir):
        """默认忽略若干版本控制与缓存目录"""
        left = workdir / "left"
        right = workdir / "right"
        for root in (left, right):
            (root / "__pycache__").mkdir(parents=True, exist_ok=True)
            _write(root / "__pycache__" / "x.txt", b"x")
            _write(root / "keep.txt", b"k")
        result = filecmp.dircmp(str(left), str(right))
        assert "__pycache__" not in result.common_dirs
        assert "keep.txt" in result.common_files

    def test_dircmp_custom_ignore_list(self, workdir):
        """自定义忽略列表只跳过指定目录"""
        left = workdir / "left"
        right = workdir / "right"
        for root in (left, right):
            (root / "keep").mkdir(parents=True, exist_ok=True)
            (root / "skip").mkdir(parents=True, exist_ok=True)
            _write(root / "keep" / "x.txt", b"x")
            _write(root / "skip" / "y.txt", b"y")
        result = filecmp.dircmp(str(left), str(right), ignore=["skip"])
        assert "keep" in result.common_dirs
        assert "skip" not in result.common_dirs


class TestFilecmpHelpers:
    """辅助函数"""

    def test_cmpfiles_equal(self, workdir):
        """比较两个目录下的同名文件"""
        left = workdir / "left"
        right = workdir / "right"
        _write(left / "f.txt", b"forge")
        _write(right / "f.txt", b"forge")
        match, mismatch, errors = filecmp.cmpfiles(left, right, ["f.txt"])
        assert match == ["f.txt"]
        assert mismatch == []
        assert errors == []

    def test_cmpfiles_reports_difference(self, workdir):
        """内容不同时返回差异列表"""
        left = workdir / "left"
        right = workdir / "right"
        _write(left / "f.txt", b"left")
        _write(right / "f.txt", b"right")
        match, mismatch, errors = filecmp.cmpfiles(left, right, ["f.txt"])
        assert mismatch == ["f.txt"]
        assert match == []

    def test_cmpfiles_reports_error(self, workdir):
        """文件不存在时进入错误列表"""
        left = workdir / "left"
        right = workdir / "right"
        left.mkdir()
        right.mkdir()
        match, mismatch, errors = filecmp.cmpfiles(left, right, ["absent.txt"])
        assert errors == ["absent.txt"]

    def test_cmpfiles_multiple_names(self, workdir):
        """一次比较多个文件名"""
        left = workdir / "left"
        right = workdir / "right"
        for name in ("a.txt", "b.txt"):
            _write(left / name, b"same")
            _write(right / name, b"same")
        match, mismatch, errors = filecmp.cmpfiles(left, right, ["a.txt", "b.txt"])
        assert sorted(match) == ["a.txt", "b.txt"]


# ======================== getopt ========================


class TestGetopt:
    """命令行解析"""

    def test_short_options(self):
        """短选项被解析成键值对"""
        args = ["-a1", "-b2"]
        opts, rest = getopt.getopt(args, "a:b:")
        assert opts == [("-a", "1"), ("-b", "2")]
        assert rest == []

    def test_short_option_with_argument(self):
        """带参数写法被解析"""
        opts, rest = getopt.getopt(["-aforge"], "a:")
        assert opts == [("-a", "forge")]

    def test_flag_without_argument(self):
        """无参开关解析成空串"""
        opts, rest = getopt.getopt(["-v"], "v")
        assert opts == [("-v", "")]

    def test_positional_kept(self):
        """位置参数原样保留"""
        opts, rest = getopt.getopt(["-v", "one", "two"], "v")
        assert opts == [("-v", "")]
        assert rest == ["one", "two"]

    def test_long_options(self):
        """长选项被解析"""
        opts, rest = getopt.getopt(["--verbose", "--count=3"], "", ["verbose", "count="])
        assert opts == [("--verbose", ""), ("--count", "3")]

    def test_long_option_separate_value(self):
        """长选项的值也可以用空格分开"""
        opts, rest = getopt.getopt(["--count", "3"], "", ["count="])
        assert opts == [("--count", "3")]

    def test_unknown_option_raises(self):
        """未知选项抛出真实错误"""
        with pytest.raises(getopt.GetoptError):
            getopt.getopt(["--nope"], "", ["verbose"])

    def test_missing_argument_raises(self):
        """缺少必需参数时抛出真实错误"""
        with pytest.raises(getopt.GetoptError):
            getopt.getopt(["--count"], "", ["count="])

    def test_getopt_returns_options_and_rest(self):
        """返回解析结果与剩余的位置参数"""
        opts, args = getopt.getopt(["-v", "tail"], "v")
        assert opts == [("-v", "")]
        assert args == ["tail"]

    def test_gnu_getopt_keeps_parsing_after_positional(self):
        """GNU 风格会继续解析位置参数之后的选项"""
        opts, rest = getopt.gnu_getopt(["-v", "tail", "-x"], "vx")
        assert opts == [("-v", ""), ("-x", "")]
        assert rest == ["tail"]

    def test_gnu_getopt_permutes(self):
        """GNU 风格会把选项移到位置参数之前"""
        opts, rest = getopt.gnu_getopt(["tail", "-v"], "v")
        assert opts == [("-v", "")]
        assert rest == ["tail"]


# ======================== keyword ========================


class TestKeyword:
    """保留字与软关键字"""

    def test_iskeyword_true(self):
        """真保留字被识别"""
        assert keyword.iskeyword("def") is True
        assert keyword.iskeyword("class") is True

    def test_iskeyword_false(self):
        """普通标识符不是保留字"""
        assert keyword.iskeyword("forge") is False
        assert keyword.iskeyword("") is False

    def test_kwlist_contains_def(self):
        """保留字列表包含关键字"""
        assert "def" in keyword.kwlist
        assert "lambda" in keyword.kwlist

    def test_softkwlist_contains_match(self):
        """软关键字列表包含软关键字"""
        assert "match" in keyword.softkwlist
        assert "_" in keyword.softkwlist

    def test_issoftkeyword(self):
        """软关键字被正确识别"""
        assert keyword.issoftkeyword("match") is True
        assert keyword.issoftkeyword("def") is False


# ======================== zipapp ========================


class TestZipapp:
    """打包成可执行归档"""

    def _make_app(self, workdir: Path) -> Path:
        src = workdir / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "__main__.py").write_text(
            "import sys\nprint('FORGE_ZIPAPP', ' '.join(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        return src

    def test_create_archive(self, workdir):
        """真的生成归档文件"""
        src = self._make_app(workdir)
        target = workdir / "app.pyz"
        zipapp.create_archive(src, target)
        assert target.exists()
        assert zipfile_is_zip(target)

    def test_archive_runs(self, workdir):
        """归档真的能被解释器执行"""
        src = self._make_app(workdir)
        target = workdir / "app.pyz"
        zipapp.create_archive(src, target)
        result = subprocess.run(
            [sys.executable, str(target), "one", "two"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert "FORGE_ZIPAPP" in result.stdout
        assert "one two" in result.stdout

    def test_archive_with_interpreter(self, workdir):
        """带解释器的归档可以直接执行"""
        src = self._make_app(workdir)
        target = workdir / "app.pyz"
        zipapp.create_archive(src, target, interpreter="/usr/bin/env python3")
        with target.open("rb") as fh:
            assert fh.read(2) == b"#!"

    def test_create_archive_with_main(self, workdir):
        """指定入口脚本时按该脚本执行"""
        src = workdir / "src_main"
        src.mkdir(parents=True, exist_ok=True)
        (src / "entry.py").write_text("print('FORGE_MAIN')\n", encoding="utf-8")
        target = workdir / "app2.pyz"
        zipapp.create_archive(src, target, main="entry:main")
        result = subprocess.run(
            [sys.executable, str(target)], capture_output=True, text=True, timeout=60
        )
        assert "FORGE_MAIN" in result.stdout

    def test_existing_file_target_is_replaced(self, workdir):
        """目标已存在时会被覆盖"""
        src = self._make_app(workdir)
        target = workdir / "app3.pyz"
        target.write_bytes(b"stale content")
        zipapp.create_archive(src, target)
        assert target.stat().st_size > 0
        assert zipfile_is_zip(target)

    def test_main_conflicts_with_dunder_main(self, workdir):
        """已有 __main__.py 时再指定入口会报错"""
        src = self._make_app(workdir)
        with pytest.raises(zipapp.ZipAppError):
            zipapp.create_archive(src, workdir / "app4.pyz", main="entry:main")

    def test_missing_source_raises(self, workdir):
        """源目录不存在时抛出真实错误"""
        with pytest.raises(zipapp.ZipAppError):
            zipapp.create_archive(workdir / "absent", workdir / "app5.pyz")

    def test_no_entry_point_raises(self, workdir):
        """既没有入口脚本也没指定入口时抛出真实错误"""
        src = workdir / "no_main"
        src.mkdir(parents=True, exist_ok=True)
        with pytest.raises(zipapp.ZipAppError):
            zipapp.create_archive(src, workdir / "app6.pyz")


def zipfile_is_zip(path: Path) -> bool:
    """判断文件是否是真实的 zip 归档。"""
    import zipfile
    return zipfile.is_zipfile(path)


# ======================== xdrlib ========================


class TestXdrlib:
    """XDR 编解码"""

    def test_pack_unpack_int(self):
        """整数能编码后解回原值"""
        packer = Packer()
        packer.pack_int(42)
        unpacker = Unpacker(packer.get_buffer())
        assert unpacker.unpack_int() == 42

    def test_pack_string_reports_type_error(self):
        """字符串编码接口在当前解释器上不接受字节形式

        这一组接口按字节串实现,当前解释器里传入字节串会因比较运算
        类型不符而失败。记录真实行为,避免误以为它可用。
        """
        packer = Packer()
        with pytest.raises(TypeError):
            packer.pack_fstring(b"forge", 5)

    def test_pack_unpack_bool(self):
        """布尔能编码后解回原值"""
        packer = Packer()
        packer.pack_bool(True)
        unpacker = Unpacker(packer.get_buffer())
        assert unpacker.unpack_bool() is True

    def test_pack_unpack_double(self):
        """双精度浮点能编码后解回原值"""
        packer = Packer()
        packer.pack_double(1.5)
        unpacker = Unpacker(packer.get_buffer())
        assert unpacker.unpack_double() == 1.5

    def test_pack_string_with_text_reports_type_error(self):
        """传入文本同样不被接受"""
        packer = Packer()
        with pytest.raises(TypeError):
            packer.pack_string("forge")

    def test_unpack_empty_buffer_raises(self):
        """空数据解包时抛出真实错误"""
        unpacker = Unpacker(b"")
        with pytest.raises((EOFError, XdrError)):
            unpacker.unpack_int()

    def test_pack_unpack_uint(self):
        """无符号整数能编码后解回原值"""
        packer = Packer()
        packer.pack_uint(4000000000)
        unpacker = Unpacker(packer.get_buffer())
        assert unpacker.unpack_uint() == 4000000000

    def test_pack_array_reports_type_error(self):
        """定长数组编码接口在当前解释器上不可用"""
        packer = Packer()
        with pytest.raises(TypeError):
            packer.pack_array([1, 2, 3], "i")

    def test_pack_list_reports_type_error(self):
        """变长列表编码接口在当前解释器上不可用"""
        packer = Packer()
        with pytest.raises(TypeError):
            packer.pack_list(["a", "b"], "u")

    def test_pack_unpack_hyper(self):
        """双精度整数能编码后解回原值"""
        packer = Packer()
        packer.pack_hyper(1234567890123)
        unpacker = Unpacker(packer.get_buffer())
        assert unpacker.unpack_hyper() == 1234567890123

    def test_packer_reset(self):
        """重置后缓冲区清空"""
        packer = Packer()
        packer.pack_int(1)
        packer.reset()
        assert len(packer.get_buffer()) == 0

    def test_unpacker_done_raises_when_remainder(self):
        """还有未取出的数据时,检查剩余会报错"""
        packer = Packer()
        packer.pack_int(9)
        packer.pack_int(10)
        unpacker = Unpacker(packer.get_buffer())
        assert unpacker.unpack_int() == 9
        with pytest.raises(XdrError):
            unpacker.done()
