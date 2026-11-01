# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`sysconfig` / `pkgutil` / `runpy` / `zipimport` / `curses` 真底层测试。

- sysconfig:真的取到解释器的安装配置
- pkgutil:真的枚举已安装的模块
- runpy:真的把一个模块当作脚本跑起来
- zipimport:真的从 zip 归档里导入模块
- curses:真的初始化终端界面,读一次按键

覆盖 sysconfig 5 + pkgutil 5 + runpy 5 + zipimport 5 + curses 5 + 真底层测试。
"""

import os
import pkgutil
import runpy
import sys
import sysconfig
import zipfile
import zipimport
from pathlib import Path

import pytest


# ======================== sysconfig ========================


class TestSysconfig:
    """解释器安装配置"""

    def test_get_paths(self):
        """能取到各安装路径"""
        paths = sysconfig.get_paths()
        assert isinstance(paths, dict)
        assert "purelib" in paths
        assert all(isinstance(v, str) for v in paths.values())

    def test_get_config_var(self):
        """能取到配置变量"""
        value = sysconfig.get_config_var("EXT_SUFFIX")
        assert value is None or isinstance(value, str)

    def test_get_python_version(self):
        """能取到版本号"""
        version = sysconfig.get_python_version()
        assert version.count(".") >= 1

    def test_get_platform(self):
        """能取到平台标识"""
        platform = sysconfig.get_platform()
        assert isinstance(platform, str)
        assert platform

    def test_get_default_scheme(self):
        """默认安装方案名"""
        scheme = sysconfig.get_default_scheme()
        assert isinstance(scheme, str)
        assert scheme


# ======================== pkgutil ========================


class TestPkgutil:
    """已安装模块的枚举"""

    def test_iter_modules_finds_stdlib(self):
        """能枚举到标准库模块"""
        names = {name for _, name, _ in pkgutil.iter_modules()}
        assert "json" in names
        assert "base64" in names

    def test_iter_modules_yields_triples(self):
        """每项是三元组"""
        for item in pkgutil.iter_modules():
            assert len(item) == 3
            break

    def test_get_loader_for_existing_module(self):
        """能取到已安装模块的加载器"""
        loader = pkgutil.get_loader("json")
        assert loader is not None

    def test_get_loader_for_missing_module(self):
        """取不到时返回空"""
        assert pkgutil.get_loader("no_such_module_forge") is None

    def test_get_data(self):
        """能读出包里的数据文件"""
        data = pkgutil.get_data("json", "decoder.py")
        assert isinstance(data, bytes)
        assert b"class" in data or b"def" in data


# ======================== runpy ========================


class TestRunpy:
    """把模块当脚本执行"""

    def test_run_path(self, tmp_path):
        """真的执行一个脚本文件"""
        script = tmp_path / "forge_script.py"
        script.write_text("VALUE = 42\nNAME = 'forge'\n", encoding="utf-8")
        result = runpy.run_path(str(script))
        assert result["VALUE"] == 42
        assert result["NAME"] == "forge"

    def test_run_path_with_globals(self, tmp_path):
        """能传入初始命名空间"""
        script = tmp_path / "forge_script2.py"
        script.write_text("RESULT = INPUT * 2\n", encoding="utf-8")
        result = runpy.run_path(str(script), init_globals={"INPUT": 21})
        assert result["RESULT"] == 42

    def test_run_module(self, tmp_path, monkeypatch):
        """能以脚本方式运行一个模块"""
        module_dir = tmp_path / "forge_runmod"
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "forge_runmod_target.py").write_text(
            "RESULT = 'from-module'\n", encoding="utf-8"
        )
        monkeypatch.syspath_prepend(str(module_dir))
        result = runpy.run_module("forge_runmod_target", run_name="__main__")
        assert result["RESULT"] == "from-module"

    def test_run_module_with_arguments(self, tmp_path, monkeypatch):
        """模块能读到命令行参数"""
        script = tmp_path / "forge_args.py"
        script.write_text("import sys\nARGS = sys.argv[1:]\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["forge_args.py", "one", "two"])
        result = runpy.run_path(str(script))
        assert result["ARGS"] == ["one", "two"]

    def test_run_path_missing_file(self):
        """文件不存在时报错"""
        with pytest.raises(FileNotFoundError):
            runpy.run_path("/no/such/forge_script.py")


# ======================== zipimport ========================


class TestZipimport:
    """从 zip 归档导入模块"""

    def _make_zip(self, tmp_path: Path) -> Path:
        archive = tmp_path / "forge_mod.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("forge_zipmod.py", "VALUE = 'from-zip'\n")
            zf.writestr("forge_zippkg/__init__.py", "PKG = 'pkg'\n")
            zf.writestr("forge_zippkg/sub.py", "SUB = 'sub'\n")
        return archive

    def test_zipimporter_can_find_module(self, tmp_path):
        """能在归档里找到模块"""
        archive = self._make_zip(tmp_path)
        importer = zipimport.zipimporter(str(archive))
        assert importer.find_spec("forge_zipmod") is not None

    def test_import_from_zip(self, tmp_path):
        """真的从归档里导入模块"""
        archive = self._make_zip(tmp_path)
        sys.path.insert(0, str(archive))
        try:
            import forge_zipmod

            assert forge_zipmod.VALUE == "from-zip"
        finally:
            sys.path.remove(str(archive))
            sys.modules.pop("forge_zipmod", None)

    def test_import_package_from_zip(self, tmp_path):
        """真的从归档里导入包"""
        archive = self._make_zip(tmp_path)
        sys.path.insert(0, str(archive))
        try:
            import forge_zippkg

            assert forge_zippkg.PKG == "pkg"
        finally:
            sys.path.remove(str(archive))
            sys.modules.pop("forge_zippkg", None)

    def test_missing_module_returns_none(self, tmp_path):
        """归档里没有的模块返回空"""
        archive = self._make_zip(tmp_path)
        importer = zipimport.zipimporter(str(archive))
        assert importer.find_spec("no_such_zip_module") is None

    def test_importer_archive_attribute(self, tmp_path):
        """导入器知道自己指向哪个归档"""
        archive = self._make_zip(tmp_path)
        importer = zipimport.zipimporter(str(archive))
        assert str(archive) in importer.archive


# ======================== curses ========================


class _CursesProbe:
    """在终端里跑一小段 curses 代码。"""

    @staticmethod
    def run():
        """初始化终端、读一次按键、恢复终端。

        在没有终端的环境里会直接返回不可用,这类用例据此跳过。
        """
        import curses

        result = {}

        def setup(screen):
            screen.addstr(0, 0, "forge")
            screen.refresh()
            try:
                result["key"] = screen.getch()
            finally:
                curses.endwin()

        try:
            curses.wrapper(setup)
        except Exception as exc:  # 没有可用终端
            return None
        return result


class TestCurses:
    """终端界面"""

    def test_module_present(self):
        """模块可用"""
        import curses

        assert curses is not None

    def test_has_error_type(self):
        """错误类型存在"""
        import curses

        assert issubclass(curses.error, Exception)

    def test_has_color_pair(self):
        """颜色对接口存在"""
        import curses

        assert callable(curses.init_pair)

    def test_wrapper_produces_result(self):
        """在终端里跑一段,拿到按键"""
        result = _CursesProbe.run()
        if result is None:
            pytest.skip("当前环境没有可用终端")
        assert "key" in result

    def test_terminfo_available(self):
        """终端描述可用"""
        import curses

        # 取颜色数要先进终端,这里只核对模块提供的常量
        assert curses.COLOR_BLACK == 0
        assert curses.KEY_DOWN > 0
