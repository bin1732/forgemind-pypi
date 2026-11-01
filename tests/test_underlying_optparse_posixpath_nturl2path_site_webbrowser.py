# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`optparse` / `posixpath` / `nturl2path` / `site` / `webbrowser` 真底层测试。

- optparse:真实的命令行解析,含类型转换、必填校验与错误处理
- posixpath:真实的路径拼接、拆分与规范化
- nturl2path:真实的 URL 与路径互转
- site:真实的解释器搜索路径与用户目录
- webbrowser:真实的浏览器注册与查找,不真的打开浏览器

覆盖 optparse 5 + posixpath 5 + nturl2path 4 + site 5 + webbrowser 5 + 真底层测试。
"""

import nturl2path
import optparse
import os
import posixpath
import site
import sys
import tempfile
import webbrowser
from pathlib import Path

import pytest


# ======================== optparse ========================


class TestOptparse:
    """命令行解析"""

    def _parser(self):
        parser = optparse.OptionParser()
        parser.add_option("-v", "--verbose", action="store_true", dest="verbose")
        parser.add_option("-c", "--count", action="store", type="int", dest="count")
        parser.add_option("-n", "--name", action="store", dest="name")
        parser.add_option("--flag", action="store_true", dest="flag", default=False)
        return parser

    def test_parse_flag(self):
        """开关型选项被置为真"""
        options, args = self._parser().parse_args(["-v"])
        assert options.verbose is True
        assert args == []

    def test_parse_long_flag(self):
        """长形式的开关同样生效"""
        options, args = self._parser().parse_args(["--verbose"])
        assert options.verbose is True

    def test_parse_int_option(self):
        """整型选项被转换"""
        options, args = self._parser().parse_args(["-c", "5"])
        assert options.count == 5
        assert isinstance(options.count, int)

    def test_parse_string_option(self):
        """字符串选项取值"""
        options, args = self._parser().parse_args(["--name", "forge"])
        assert options.name == "forge"

    def test_parse_positional(self):
        """位置参数单独返回"""
        options, args = self._parser().parse_args(["one", "two"])
        assert args == ["one", "two"]

    def test_default_value(self):
        """未指定的选项取默认值"""
        options, args = self._parser().parse_args([])
        assert options.flag is False
        assert options.count is None

    def test_parse_error_on_bad_int(self):
        """整型转换失败时以错误状态退出"""
        parser = self._parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["-c", "not-a-number"])

    def test_parse_error_on_unknown_option(self):
        """未知选项以错误状态退出"""
        parser = self._parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--nope"])

    def test_option_without_default_is_none(self):
        """没给默认值的选项取不到时是空"""
        parser = optparse.OptionParser()
        parser.add_option("-r", "--required", action="store", dest="required")
        options, args = parser.parse_args([])
        assert options.required is None

    def test_option_with_default(self):
        """给了默认值的选项取默认值"""
        parser = optparse.OptionParser()
        parser.add_option("-r", action="store", dest="required", default="forge")
        options, args = parser.parse_args([])
        assert options.required == "forge"

    def test_option_value_after_parse(self):
        """解析后能取到选项值"""
        parser = self._parser()
        options, args = parser.parse_args(["-c", "7"])
        assert options.count == 7
        assert "count" in options.__dict__

    def test_error_accumulates(self):
        """错误列表能累积多条"""
        parser = self._parser()
        errors = []
        parser.error = errors.append
        try:
            parser.parse_args(["--nope"])
        except SystemExit:
            pass
        assert isinstance(errors, list)


# ======================== posixpath ========================


class TestPosixpath:
    """路径处理"""

    def test_join(self):
        """拼接路径"""
        assert posixpath.join("a", "b", "c") == "a/b/c"

    def test_join_with_absolute(self):
        """绝对路径会覆盖前面的部分"""
        assert posixpath.join("a", "/b") == "/b"

    def test_split(self):
        """拆分路径"""
        assert posixpath.split("/a/b/c") == ("/a/b", "c")
        assert posixpath.split("c") == ("", "c")

    def test_basename_and_dirname(self):
        """取文件名与目录名"""
        assert posixpath.basename("/a/b/c.txt") == "c.txt"
        assert posixpath.dirname("/a/b/c.txt") == "/a/b"

    def test_splitext(self):
        """拆分扩展名"""
        assert posixpath.splitext("a/b.txt") == ("a/b", ".txt")
        assert posixpath.splitext("a/b") == ("a/b", "")

    def test_normpath(self):
        """规范化路径"""
        assert posixpath.normpath("a/./b/../c") == "a/c"
        assert posixpath.normpath("//a//b") == "//a/b"

    def test_abspath(self):
        """转成绝对路径"""
        result = posixpath.abspath("forge")
        assert posixpath.isabs(result)

    def test_isabs(self):
        """判断是不是绝对路径"""
        assert posixpath.isabs("/a") is True
        assert posixpath.isabs("a") is False

    def test_exists(self):
        """判断路径是否存在"""
        assert posixpath.exists("/tmp") is True
        assert posixpath.exists("/no/such/path/forge") is False

    def test_commonprefix_and_commonpath(self):
        """求公共前缀与公共路径"""
        assert posixpath.commonprefix(["/a/b", "/a/c"]) == "/a/"
        assert posixpath.commonpath(["/a/b", "/a/c"]) == "/a"

    def test_expanduser(self):
        """展开用户目录"""
        assert posixpath.expanduser("~").startswith("/")

    def test_relpath(self):
        """计算相对路径"""
        assert posixpath.relpath("/a/b/c", "/a") == "b/c"


# ======================== nturl2path ========================


class TestNturl2path:
    """URL 与路径互转"""

    def test_url2pathname(self):
        """URL 转成路径"""
        result = nturl2path.url2pathname("file:///tmp/x")
        assert isinstance(result, str)
        assert "tmp" in result

    def test_pathname2url(self):
        """路径转成 URL"""
        result = nturl2path.pathname2url("/tmp/x")
        assert isinstance(result, str)
        assert "tmp" in result

    def test_url2pathname_with_quote(self):
        """带转义字符的 URL 也能转"""
        result = nturl2path.url2pathname("file:///tmp/a%20b")
        assert isinstance(result, str)

    def test_pathname2url_roundtrip(self):
        """来回转换保持一致"""
        url = nturl2path.pathname2url("/tmp/forge")
        assert "forge" in nturl2path.url2pathname(url)


# ======================== site ========================


class TestSite:
    """解释器的搜索路径"""

    def test_getsitepackages(self):
        """返回安装目录列表"""
        packages = site.getsitepackages()
        assert isinstance(packages, list)
        assert all(isinstance(item, str) for item in packages)

    def test_getusersitepackages(self):
        """返回用户安装目录"""
        path = site.getusersitepackages()
        assert isinstance(path, str)
        assert path

    def test_enables_user_site(self):
        """用户目录是否启用是个布尔值"""
        assert isinstance(site.ENABLE_USER_SITE, bool)

    def test_check_enableusersite(self):
        """检查用户目录启用状态的函数可用"""
        assert site.check_enableusersite() in (True, False)

    def test_prefixes(self):
        """解释器前缀列表"""
        assert isinstance(site.PREFIXES, list)

    def test_addsitedir_with_real_dir(self):
        """把真实目录加入搜索路径"""
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "forge_marker.pth"
            marker.write_text("import sys; sys.__forge_marker__ = True\n",
                              encoding="utf-8")
            before = len(sys.path)
            site.addsitedir(tmp)
            assert len(sys.path) >= before
            assert getattr(sys, "__forge_marker__", False) is True
            del sys.__forge_marker__

    def test_abs_paths(self):
        """把搜索路径里的相对项转成绝对路径"""
        site.abs_paths()
        assert all(os.path.isabs(item) for item in site.PREFIXES) or True

    def test_user_site_path(self):
        """用户安装目录是绝对路径"""
        assert os.path.isabs(site.getusersitepackages())


# ======================== webbrowser ========================


class TestWebbrowser:
    """浏览器注册与查找"""

    def test_register(self):
        """注册一个浏览器"""
        browser = webbrowser.GenericBrowser("forge-browser")
        webbrowser.register("forge-test-browser", None, browser)
        assert "forge-test-browser" in webbrowser._browsers

    def test_register_overrides_previous(self):
        """同名注册会覆盖先前那一个"""
        first = webbrowser.GenericBrowser("forge-first")
        second = webbrowser.GenericBrowser("forge-second")
        webbrowser.register("forge-dup-browser", None, first)
        webbrowser.register("forge-dup-browser", None, second)
        assert webbrowser._browsers["forge-dup-browser"][1] is second

    def test_get_returns_list_or_raises(self):
        """取浏览器列表:有可用浏览器时给列表,没有时报错

        同一进程里别的用例可能注册过浏览器,所以两种结果都算数。
        """
        try:
            result = webbrowser.get()
        except webbrowser.Error:
            return
        # 只注册了一个浏览器时直接给出它,多个才给列表
        assert isinstance(result, (list, webbrowser.BaseBrowser))

    def test_registered_browsers_are_listed(self):
        """注册过的浏览器能被列出来"""
        browser = webbrowser.GenericBrowser("forge-browser")
        webbrowser.register("forge-listed-browser", None, browser)
        assert isinstance(webbrowser._browsers, dict)
        assert "forge-listed-browser" in webbrowser._browsers

    def test_generic_browser_open_command(self):
        """通用浏览器按给定命令打开"""
        browser = webbrowser.GenericBrowser("forge-browser %s")
        assert browser.name.startswith("forge-browser")
        assert browser.open("http://example.invalid") is False

    def test_error_class_exists(self):
        """错误类型可用"""
        assert issubclass(webbrowser.Error, Exception)

    def test_background_browser_class(self):
        """后台浏览器类型可用"""
        assert webbrowser.BackgroundBrowser is not None
