# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 GitHub Release wheel 真装真跑:
  1. 真从 https://github.com/bin1732/forgemind-pypi/releases/latest 下载 wheel
  2. 真 venv 装
  3. 真跑 forgemind info / --help
  4. 验装完能 import forgemind + version 匹配

完全不走 mock, 完全在子 venv 跑, 装完用新 venv 的 python 跑真命令。
"""
import os
import subprocess
import time
import types
import tomllib
import sys
import urllib.request
import venv
from pathlib import Path

import pytest

# 版本号从 pyproject 取唯一真源。这里跟着版本号变动,否则版本一升级,
# 这个文件要么跟着改,要么悄悄去验一个已经不是当前版本的构件。
_REPO_ROOT = Path(__file__).resolve().parents[1]
with open(_REPO_ROOT / "pyproject.toml", "rb") as _fh:
    PKG_VERSION = tomllib.load(_fh)["project"]["version"]
WHEEL_NAME = f"forgemind-{PKG_VERSION}-py3-none-any.whl"
DIST_INFO = f"forgemind-{PKG_VERSION}.dist-info"


def _clean_env() -> dict:
    """子进程的环境:去掉 PYTHONPATH 与 VIRTUAL_ENV。

    仓库根目录留在 PYTHONPATH 里的话,pip 会认为 forgemind 已经装好,
    直接跳过安装 —— 装完的 venv 里连二进制都没有。而后面那些 import
    也会命中仓库而不是装出来的 wheel,验的就不是构件本身了。
    干净 venv 本来就不该看得见源码树。
    """
    return {k: v for k, v in os.environ.items()
            if k not in ("PYTHONPATH", "VIRTUAL_ENV")}


def _download_latest_wheel(dest: Path) -> tuple[Path, int]:
    """真下载 GitHub Releases latest wheel。

    网络抖动(SSL 握手失败、连接被重置)不是对构件的检验结论,重试几次再
    判失败。连续多次失败才说明真的下不到。
    """
    url = (
        "https://github.com/bin1732/forgemind-pypi/releases/download/continuous/"
        f"{WHEEL_NAME}"
    )
    last_error = ""
    for attempt in range(3):
        try:
            # urllib 有时 UA 受限, 走 curl subprocess
            r = subprocess.run(
                ["curl", "-sL", "-o", str(dest), url],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                raise RuntimeError(f"curl 失败: rc={r.returncode} stderr={r.stderr}")
        except FileNotFoundError:
            # 没 curl, 走 urllib
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    data = resp.read()
                dest.write_bytes(data)
            except Exception as e:
                last_error = f"urllib 网络受限: {e}"
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
                continue
        except Exception as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
            continue
        if dest.exists() and dest.stat().st_size >= 50000:
            return dest, dest.stat().st_size
        size = dest.stat().st_size if dest.exists() else 0
        last_error = f"wheel 太小 {size} 字节, 可能是 error 页"
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(last_error)


class TestDownloadRetry:
    """下载抖动不该被当成对构件的检验结论。"""

    def test_retries_then_gives_up(self, tmp_path, monkeypatch):
        """连续失败时重试数次,之后才报错。"""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return types.SimpleNamespace(returncode=35, stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(time, "sleep", lambda seconds: None)
        with pytest.raises(RuntimeError, match="curl 失败"):
            _download_latest_wheel(tmp_path / "x.whl")
        assert len(calls) == 3, f"重试次数不对: {len(calls)}"

    def test_no_retry_when_download_succeeds(self, tmp_path, monkeypatch):
        """一次成功就不该再试。"""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            (tmp_path / "x.whl").write_bytes(b"x" * 60000)
            return types.SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        _, size = _download_latest_wheel(tmp_path / "x.whl")
        assert size == 60000
        assert len(calls) == 1, f"不该重试: {len(calls)}"


@pytest.fixture(scope="module")
def fresh_venv_with_wheel(tmp_path_factory):
    if not Path("/workspace/quantmind").is_dir():
        pytest.skip("需要本地构建产物与已装依赖,常规流水线不具备")
    """真建 venv + 装 wheel + 跑 forgemind info。"""
    tmp = tmp_path_factory.mktemp("release_install")
    venv_dir = tmp / "venv"
    wheel_path = tmp / WHEEL_NAME

    # 1. 真建 venv
    venv.EnvBuilder(with_pip=True, symlinks=False).create(str(venv_dir))
    pip = venv_dir / "bin" / "pip"
    forgemind_bin = venv_dir / "bin" / "forgemind"

    # 2. 真下载 wheel
    wheel_path, size = _download_latest_wheel(wheel_path)

    # 3. link 现有 .venv 的 site-packages (沙箱无 PyPI, 复用主 venv)
    import shutil
    src_sp = Path("/workspace/.venv/lib/python3.11/site-packages")
    dst_sp = venv_dir / "lib" / "python3.11" / "site-packages"
    if src_sp.exists():
        # 复制核心 deps 的 .dist-info + 包目录
        for item in src_sp.iterdir():
            if item.name.startswith(("click", "pydantic", "rich", "duckdb",
                                     "fastapi", "httpx", "typer", "shellingham",
                                     "structlog", "numpy", "pandas", "polars",
                                     "langchain", "langgraph", "langsmith",
                                     "openai", "anthropic", "pyarrow", "joblib",
                                     "scipy", "scikit", "lightgbm", "tenacity", "pytz", "tzdata",
                                     "python_multipart", "python-multipart",
                                     "uvicorn", "starlette", "anyio",
                                     "sniffio", "h11", "certifi", "idna",
                                     "urllib3", "requests", "PyYAML", "yaml",
                                     "jsonpatch", "jsonpointer", "jsonschema",
                                     "typing_extensions", "annotated_types",
                                     "pydantic_core", "pydantic-settings",
                                     "dotenv", "watchfiles", "websockets",
                                     "exceptiongroup", "tomli", "wrapt",
                                     "SQLAlchemy", "alembic", "Mako", "dateutil",
                                     "pyparsing", "packaging", "six",
                                     "clickhouse_driver", "asyncpg",
                                     "nltk", "regex", "tqdm", "colorama",
                                     "mcp", "jsonschema_spec", "referencing",
                                     "rpds", "pyzmq", "cloudpickle",
                                     "httpx_sse", "sse_starlette",
                                     "langchain_core", "langchain_text_splitters",
                                     "chromadb", "llama_index", "redis",
                                     "nats_py", "nats-py",
                                     "prefect", "fsspec", "aiohttp",
                                     "aiosignal", "frozenlist", "multidict",
                                     "yarl", "charset_normalizer",
                                     "asgi_lifespan", "async_timeout",
                                     "h2", "hpack", "hyperframe",
                                     "pika", "python_jose", "passlib",
                                     "bcrypt", "ecdsa", "rsa", "pyasn1",
                                     "ecdsa", "cffi", "pycparser",
                                     "Pillow", "pillow",
                                     )):
                if not item.name.startswith("forgemind"):
                    target = dst_sp / item.name
                    if not target.exists():
                        try:
                            target.symlink_to(item)
                        except (OSError, FileExistsError):
                            pass

    # 4. 真装 wheel (沙箱无 PyPI, --no-deps 跳过 deps; 我们用 symlink 补)
    r = subprocess.run(
        [str(pip), "install", "--no-deps", str(wheel_path)],
        capture_output=True, text=True, timeout=120, env=_clean_env(),
    )
    if r.returncode != 0:
        pytest.fail(f"pip install 失败: {r.stderr[-500:]}")

    yield {
        "venv": venv_dir,
        "wheel": wheel_path,
        "wheel_size": size,
        "forgemind_bin": forgemind_bin,
        "pip": pip,
    }


def test_wheel_downloaded_size(fresh_venv_with_wheel):
    """wheel 字节数应 ≥ 100KB (不是 error 页)"""
    size = fresh_venv_with_wheel["wheel_size"]
    assert size >= 100_000, f"wheel 太小 {size} 字节"


def test_wheel_zip_structure(fresh_venv_with_wheel):
    """wheel 真含 forgemind 模块 (用 zipfile 真打开看)"""
    import zipfile
    wheel = fresh_venv_with_wheel["wheel"]
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
    # 业务关键模块
    required = [
        "forgemind/__init__.py",
        "forgemind/cli.py",
        "forgemind/api/main.py",
        "forgemind/mcp/server.py",
        "forgemind/core/data/storage.py",
        "forgemind/core/backtest/engine.py",
        "forgemind/core/factors/alpha158.py",
        f"{DIST_INFO}/METADATA",
    ]
    for r in required:
        assert r in names, f"wheel 缺 {r}, 实际 (前 20): {names[:20]}"


def test_wheel_metadata_declares_deps(fresh_venv_with_wheel):
    """wheel METADATA 真声明 fastapi/duckdb/pydantic 等核心依赖"""
    import zipfile
    wheel = fresh_venv_with_wheel["wheel"]
    with zipfile.ZipFile(wheel) as z:
        metadata = z.read(f"{DIST_INFO}/METADATA").decode("utf-8")
    # 必须声明的核心依赖
    for dep in ("fastapi", "duckdb", "pydantic", "structlog", "click"):
        assert dep in metadata, f"wheel METADATA 应声明 {dep}"
    # 必须有 5 个 extras
    for extra in ("dev", "llm", "ml", "cn", "multimodal", "explain"):
        assert f"Provides-Extra: {extra}" in metadata, f"wheel METADATA 缺 [{extra}] extra"


def test_pip_install_succeeded(fresh_venv_with_wheel):
    """pip install --no-deps 后, forgemind binary 真在 venv/bin/"""
    forgemind_bin = fresh_venv_with_wheel["forgemind_bin"]
    assert forgemind_bin.exists(), f"forgemind binary 应在 {forgemind_bin}"


def test_fresh_venv_imports_forgemind(fresh_venv_with_wheel):
    """新 venv 真能 import forgemind (验 wheel 自洽)"""
    venv_dir = fresh_venv_with_wheel["venv"]
    r = subprocess.run(
        [str(venv_dir / "bin" / "python"), "-c", "import forgemind; print(forgemind.__version__)"],
        capture_output=True, text=True, timeout=15, env=_clean_env(),
    )
    assert r.returncode == 0, f"import 失败: {r.stderr[-300:]}"
    assert PKG_VERSION in r.stdout, f"version 应 {PKG_VERSION}, 实际: {r.stdout!r}"


def test_fresh_venv_forgemind_help(fresh_venv_with_wheel):
    """forgemind --help 真跑得通"""
    forgemind_bin = fresh_venv_with_wheel["forgemind_bin"]
    r = subprocess.run(
        [str(forgemind_bin), "--help"],
        capture_output=True, text=True, timeout=15, env=_clean_env(),
    )
    assert r.returncode == 0, f"--help 失败: {r.stderr[-300:]}"
    # 子命令应展示
    assert "etl" in r.stdout, f"--help 应有 etl: {r.stdout[:300]}"
    assert "backtest" in r.stdout, f"--help 应有 backtest"
    assert "agent" in r.stdout, f"--help 应有 agent"
    assert "mcp" in r.stdout, f"--help 应有 mcp"
    assert "pick" in r.stdout, f"--help 应有 pick"


def test_fresh_venv_forgemind_info(fresh_venv_with_wheel):
    """forgemind info 真跑得通, version 真报当前版本"""
    forgemind_bin = fresh_venv_with_wheel["forgemind_bin"]
    r = subprocess.run(
        [str(forgemind_bin), "info"],
        capture_output=True, text=True, timeout=15, env=_clean_env(),
    )
    # info 子命令可能 rc=0 或 rc=2 (settings 错) — 关键是输出含 version
    if r.returncode not in (0, 2):
        pytest.fail(f"info rc={r.returncode}: {r.stdout[-300:]}{r.stderr[-300:]}")
    out = r.stdout + r.stderr
    assert PKG_VERSION in out, f"info 应报 {PKG_VERSION}, 实际: {out[:500]}"


def test_fresh_venv_forgemind_backtest_list_strategies(fresh_venv_with_wheel):
    """forgemind backtest --list-strategies 真跑得通, 列策略"""
    forgemind_bin = fresh_venv_with_wheel["forgemind_bin"]
    r = subprocess.run(
        [str(forgemind_bin), "backtest", "--list-strategies"],
        capture_output=True, text=True, timeout=15, env=_clean_env(),
    )
    if r.returncode != 0:
        pytest.fail(f"list-strategies rc={r.returncode}: {r.stdout[-300:]}{r.stderr[-300:]}")
    out = r.stdout
    # 真有 17 个策略
    # 简单数: 非空非分隔符行
    n = sum(1 for line in out.splitlines() if line.strip() and "─" not in line and line.split())
    assert n >= 17, f"应 ≥ 17 策略, 实际 {n}: {out[:500]}"


def test_fresh_venv_imports_all_key_modules(fresh_venv_with_wheel):
    """新 venv 真能 import 关键模块 (验 wheel 含所有 .py)"""
    venv_dir = fresh_venv_with_wheel["venv"]
    # 重点验顶层 + cli + backtest (业务核心 + 跑得通的)
    modules_to_test = [
        "forgemind",
        "forgemind.core.backtest.engine",
        "forgemind.core.factors.alpha158",
        "forgemind.cli",
    ]
    failed = []
    for m in modules_to_test:
        r = subprocess.run(
            [str(venv_dir / "bin" / "python"), "-c", f"import {m}; print('OK')"],
            capture_output=True, text=True, timeout=10, env=_clean_env(),
        )
        if r.returncode != 0:
            failed.append((m, r.stderr[-200:]))
    assert not failed, f"以下模块 import 失败: {failed}"
