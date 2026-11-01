# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""README 里的命令必须真的能跑

README 写
    pip install --extra-index-url .../pypi/simple/forgemind/ forgemind
pip 会把项目名再拼一次,实际请求 .../simple/forgemind/forgemind/ → 404,
用户照抄得到 "No matching distribution found"。

只用 curl 验过 URL 可达并不足以说明问题,**必须真跑过 pip** ——
这类"看起来对"的文档缺陷只能靠真执行发现。
"""

import re
import subprocess
import time
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


# 标了这句话的命令是**故意写错的示范**,不参与核对
ERROR_EXAMPLE_MARK = "错误示范"


def _readme_commands(prefix="pip install", include_error_examples: bool = False):
    """README 里的命令行。

    FAQ 里有一条故意写错的安装命令(示范 --index-url 为什么不行)。
    它不参与核对 —— 但它必须**确实是错的**,否则那条警告就白写了。
    """
    text = README.read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        if ERROR_EXAMPLE_MARK in stripped and not include_error_examples:
            continue
        out.append(stripped)
    return out


class TestReadmeInstallCommand:
    def test_readme_has_install_command(self):
        assert _readme_commands(), "README 里没有 pip install 命令"

    def test_index_url_has_no_trailing_project_name(self):
        """--index-url / --extra-index-url 不能以 /<项目名> 结尾

        pip 会自己拼上项目名,带了就会变成 .../forgemind/forgemind/。
        """
        for cmd in _readme_commands():
            for flag in ("--index-url", "--extra-index-url"):
                for m in re.finditer(rf"{flag}\s+(\S+)", cmd):
                    url = m.group(1)
                    assert not url.rstrip("/").endswith("/forgemind"), (
                        f"{flag} 带了项目名,pip 会再拼一次导致 404: {url}\n"
                        f"  命令: {cmd}"
                    )

    @pytest.mark.slow
    def test_install_command_actually_resolves(self, tmp_path):
        """真跑一次 pip(只解析不安装),确认用户能装上"""
        cmd = _readme_commands()[0]
        # 真连网络,天然会抖:索引刚切换、CDN 还没同步、或者某一次连接中断,
        # 都会让一次下载失败。给有界重试 —— 不重试就是随机红,重试不是
        # 掩盖:两次都失败才判失败。
        dl = cmd.replace(
            "pip install",
            f"{sys.executable} -m pip download --no-deps "
            f"--retries 5 --timeout 60 -d {tmp_path}",
        )
        last = None
        for attempt in range(2):
            r = subprocess.run(
                dl, shell=True, capture_output=True, text=True, timeout=420
            )
            if r.returncode == 0 and list(tmp_path.glob("*.whl")):
                return
            last = r
            time.sleep(5)
        assert last.returncode == 0, (
            f"README 的安装命令执行失败:\n  {cmd}\n"
            f"{(last.stdout or '')[-400:]}\n{(last.stderr or '')[-400:]}"
        )
        assert list(tmp_path.glob("*.whl")), "命令成功但没拿到 wheel"


class TestReadmeClaimsMatchCode:
    def test_no_dead_links_to_missing_files(self):
        text = README.read_text(encoding="utf-8")
        for m in re.finditer(r"\]\((?!https?://)([^)#]+)\)", text):
            target = m.group(1).strip()
            if not (ROOT / target).exists():
                pytest.fail(f"README 存在死链: ({target})")

    def test_no_docker_claim_without_dockerfile(self):
        text = README.read_text(encoding="utf-8")
        if "docker run" in text:
            assert (ROOT / "Dockerfile").exists(), (
                "README 提到 docker run,但仓库里没有 Dockerfile"
            )

    def test_test_file_count_is_accurate(self):
        text = README.read_text(encoding="utf-8")
        m = re.search(r"(\d+)\s+test files", text)
        if m:
            actual = len(list((ROOT / "tests").glob("test_*.py")))
            assert actual == int(m.group(1)), (
                f"README 称 {m.group(1)} 个测试文件,实际 {actual}"
            )


class TestReadmeInstallCommandResolvesDependencies:
    """--index-url 与 --extra-index-url 的差别不是风格问题

    `--index-url` **替换**默认源,于是 pip 会去我们的索引里找 fastapi、
    duckdb 这些依赖 —— 全部 "No matching distribution found"。
    `--extra-index-url` 才是在默认源旁边**追加**我们的索引。

    该缺陷之所以能留存:README 上写着"以上命令在全新 venv 中
    已验证通过",而实际只 curl 过一次 URL。声明是真的,命令是假的。
    """

    def test_install_command_uses_extra_index_url(self):
        """用 --index-url 的命令在真实环境里装不上,一个都不许有"""
        for cmd in _readme_commands():
            assert "--index-url" not in cmd or "--extra-index-url" in cmd, (
                f"README 的安装命令用了 --index-url,依赖会解析失败:\n  {cmd}\n"
                "  应改为 --extra-index-url(在 PyPI 旁边追加我们的索引)"
            )

    def test_cli_etl_docs_mention_the_cn_extra(self):
        """`forgemind etl` 需要 akshare,它只在 [cn] extra 里"""
        text = README.read_text(encoding="utf-8")
        if "forgemind etl" not in text:
            pytest.skip("README 未展示 etl 命令")
        assert "forgemind[cn]" in text, (
            "README 直接教用户跑 forgemind etl,却没给出装 [cn] extra 的命令 —— "
            "照抄必然得到 akshare_not_installed"
        )

    def test_declared_etl_dependency_is_reachable_from_the_documented_command(self):
        """pyproject 里声明的东西,必须有一条文档化的路径能装上它"""
        import tomllib

        meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        extras = meta.get("project", {}).get("optional-dependencies", {})
        cn = extras.get("cn", [])
        assert any("akshare" in d for d in cn), (
            "etl 依赖 akshare,若它不在 [cn] 里,就必须挪到核心依赖"
        )
        assert "forgemind[cn]" in README.read_text(encoding="utf-8"), (
            "akshare 在 [cn] extra,README 必须给出安装它的命令"
        )
