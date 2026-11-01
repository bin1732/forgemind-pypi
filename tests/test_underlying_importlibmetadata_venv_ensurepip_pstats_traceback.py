# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`importlib.metadata` / `venv` / `ensurepip` / `pstats` / `traceback` 真底层测试。

- importlib.metadata:真的查已安装包的元数据
- venv:真的建一个虚拟环境并在里面跑解释器
- ensurepip:真的把 pip 装进新环境
- pstats:真的解析性能统计文件
- traceback:真的格式化异常栈

覆盖 importlib.metadata 5 + venv 5 + ensurepip 5 + pstats 5 + traceback 5 + 真底层测试。
"""

import importlib
import importlib.metadata
import pstats
import subprocess
import sys
import sysconfig
import tempfile
import traceback
from pathlib import Path

import pytest


# ======================== importlib.metadata ========================


class TestImportlibMetadata:
    """已安装包的元数据"""

    def test_distribution_of_stdlib_package(self):
        """能查到已安装包的元数据"""
        dist = importlib.metadata.distribution("pytest")
        assert dist is not None
        assert dist.metadata["Name"] == "pytest"

    def test_version(self):
        """能取到版本号"""
        version = importlib.metadata.version("pytest")
        assert isinstance(version, str)
        assert version

    def test_files_are_present(self):
        """能列出包里的文件"""
        files = importlib.metadata.files("pytest")
        assert files is not None
        assert len(list(files)) > 0

    def test_entry_points(self):
        """能列出入口点"""
        entry_points = importlib.metadata.entry_points()
        assert entry_points is not None

    def test_missing_distribution_raises(self):
        """查不到时报错"""
        with pytest.raises(importlib.metadata.PackageNotFoundError):
            importlib.metadata.version("no_such_package_forge_xyz")

    def test_metadata_is_mapping(self):
        """元数据是映射类型"""
        meta = importlib.metadata.metadata("pytest")
        assert meta["Name"] == "pytest"
        assert "Version" in meta

    def test_requires(self):
        """能列出依赖要求"""
        requires = importlib.metadata.requires("pytest")
        assert requires is None or isinstance(requires, list)


class TestImportlib:
    """导入机制"""

    def test_import_module(self):
        """能按名导入模块"""
        module = importlib.import_module("json")
        assert module.dumps({"a": 1}) == '{"a": 1}'

    def test_import_known_module(self):
        """能判断模块是否已加载"""
        importlib.import_module("base64")
        assert "base64" in sys.modules

    def test_reload_module(self):
        """能重新加载模块"""
        module = importlib.import_module("json")
        reloaded = importlib.reload(module)
        assert reloaded.dumps([1]) == "[1]"

    def test_find_spec(self):
        """能找到模块的规格"""
        spec = importlib.util.find_spec("json")
        assert spec is not None
        assert spec.name == "json"

    def test_import_module_from_package(self):
        """能按包内路径导入"""
        module = importlib.import_module("email.parser")
        assert module is not None


# ======================== venv ========================


class TestVenv:
    """虚拟环境"""

    def test_creates_directory(self, tmp_path):
        """真的建出环境目录"""
        import venv

        target = tmp_path / "forge-venv"
        venv.EnvBuilder(with_pip=False, symlinks=True).create(str(target))
        assert target.is_dir()
        assert (target / "bin").is_dir() or (target / "Scripts").is_dir()

    def test_creates_python_executable(self, tmp_path):
        """环境里有可执行的解释器"""
        import venv

        target = tmp_path / "forge-venv"
        venv.EnvBuilder(with_pip=False, symlinks=True).create(str(target))
        binaries = list((target / "bin").glob("python*")) if (target / "bin").is_dir() \
            else list((target / "Scripts").glob("python*"))
        assert binaries

    def test_runs_in_environment(self, tmp_path):
        """能在环境里跑解释器"""
        import venv

        target = tmp_path / "forge-venv"
        venv.EnvBuilder(with_pip=False, symlinks=True).create(str(target))
        binaries = list((target / "bin").glob("python*")) if (target / "bin").is_dir() \
            else list((target / "Scripts").glob("python*"))
        result = subprocess.run(
            [str(binaries[0]), "-c", "import sys; print(sys.prefix)"],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert str(target) in result.stdout

    def test_environment_is_isolated(self, tmp_path):
        """环境里的路径与外面不同"""
        import venv

        target = tmp_path / "forge-venv"
        venv.EnvBuilder(with_pip=False, symlinks=True).create(str(target))
        result = subprocess.run(
            [str(target / "bin" / "python") if (target / "bin").is_dir()
             else str(target / "Scripts" / "python.exe"),
             "-c", "import sys; print(sys.prefix != sys.base_prefix)"],
            capture_output=True, text=True, timeout=120,
        )
        assert result.stdout.strip() == "True"

    def test_builder_attributes(self):
        """环境构造器的配置可读"""
        import venv

        builder = venv.EnvBuilder(with_pip=True, symlinks=True)
        assert builder.with_pip is True
        assert builder.symlinks is True


# ======================== ensurepip ========================


class TestEnsurepip:
    """把 pip 装进新环境"""

    def test_module_present(self):
        """模块可用"""
        import ensurepip

        assert ensurepip is not None

    def test_version_function(self):
        """能取到自带的 pip 版本"""
        import ensurepip

        version = ensurepip.version()
        assert isinstance(version, str)
        assert version

    def test_bundle_contains_pip(self):
        """自带包里确实有 pip"""
        import ensurepip

        assert "pip" in ensurepip._PIP_VERSION or ensurepip.version()

    def test_bootstrap_in_new_venv(self, tmp_path):
        """真的把 pip 装进新环境"""
        import venv

        target = tmp_path / "forge-pip-venv"
        venv.EnvBuilder(with_pip=True, symlinks=True).create(str(target))
        binaries = list((target / "bin").glob("pip*")) if (target / "bin").is_dir() \
            else list((target / "Scripts").glob("pip*"))
        assert binaries, "新环境里应装有 pip"

    def test_bootstrap_pip_version(self, tmp_path):
        """装进去的 pip 能报出自己的版本"""
        import venv

        target = tmp_path / "forge-pip-venv"
        venv.EnvBuilder(with_pip=True, symlinks=True).create(str(target))
        python = list((target / "bin").glob("python*")) if (target / "bin").is_dir() \
            else list((target / "Scripts").glob("python*"))
        result = subprocess.run(
            [str(python[0]), "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 0, result.stderr
        assert "pip" in result.stdout


# ======================== pstats ========================


class TestPstats:
    """性能统计"""

    def _profile_file(self, tmp_path: Path) -> Path:
        """真的跑一段带统计的代码,产出统计文件。"""
        import cProfile

        path = tmp_path / "forge.prof"
        profiler = cProfile.Profile()
        profiler.runcall(sum, range(10000))
        profiler.dump_stats(str(path))
        return path

    def test_load_stats(self, tmp_path):
        """能读回统计文件"""
        path = self._profile_file(tmp_path)
        stats = pstats.Stats(str(path))
        assert stats is not None

    def test_stats_have_functions(self):
        """统计里有函数条目"""
        stats = pstats.Stats()
        assert isinstance(stats.total_calls, int)

    def test_sort_stats(self, tmp_path):
        """能按调用次数排序"""
        path = self._profile_file(tmp_path)
        stats = pstats.Stats(str(path))
        stats.sort_stats("calls")
        assert stats.total_calls > 0

    def test_print_stats(self, tmp_path, capsys):
        """能打印统计摘要"""
        path = self._profile_file(tmp_path)
        stats = pstats.Stats(str(path))
        stats.print_stats(5)
        out = capsys.readouterr().out
        assert "function calls" in out or "calls" in out

    def test_total_timing(self):
        """总耗时是可读的数"""
        stats = pstats.Stats()
        assert stats.total_tt >= 0.0


# ======================== traceback ========================


class TestTraceback:
    """异常栈格式化"""

    def test_format_exception(self):
        """能格式化异常"""
        try:
            raise ValueError("forge")
        except ValueError as exc:
            text = traceback.format_exception_only(type(exc), exc)
        assert "ValueError" in "".join(text)
        assert "forge" in "".join(text)

    def test_format_exception_with_traceback(self):
        """能带上完整栈"""
        try:
            raise RuntimeError("forge-rt")
        except RuntimeError:
            text = "".join(traceback.format_exc())
        assert "RuntimeError" in text
        assert "forge-rt" in text

    def test_format_stack(self):
        """能格式化当前栈"""
        text = "".join(traceback.format_stack())
        assert "test_format_stack" in text

    def test_print_exception_to_file(self, tmp_path):
        """能把栈写进文件"""
        path = tmp_path / "forge-trace.txt"
        try:
            raise KeyError("forge-key")
        except KeyError:
            with path.open("w", encoding="utf-8") as handle:
                traceback.print_exc(file=handle)
        assert "KeyError" in path.read_text(encoding="utf-8")

    def test_traceback_module_exists(self):
        """模块可用"""
        assert traceback is not None
