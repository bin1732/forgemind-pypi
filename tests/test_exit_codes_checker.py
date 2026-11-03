# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""退出码核对器自己得可靠。

它盯的是 README 里那张错误码表 —— 表与实际行为分家,这张表就只剩误导
作用。所以这个检查器自己也要能验:表里写错了码,它得报出来;表是对的,
它不许报。
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_exit_codes.py"

sys.path.insert(0, str(REPO / "scripts"))


def _run(readme: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(readme)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=900,
    )


class TestExitCodeChecker:
    def test_real_readme_matches_the_commands(self):
        """真的 README 与真的命令要对得上"""
        result = _run(REPO / "README.md")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_it_catches_a_wrong_table(self):
        """表里写错了码,它必须报出来

        没有这一条,这个检查器可能一直报绿 —— 那它盯的就不是那张表了。
        """
        text = (REPO / "README.md").read_text(encoding="utf-8")
        # 把"argparse 用法错误"那一行的码改成 9 —— 实际是 2
        doctored = text.replace(
            "| 2 | 参数与审批类 | argparse 用法错误",
            "| 9 | 参数与审批类 | argparse 用法错误",
        )
        assert doctored != text, "没改动 README,这条断言就落空了"
        tmp = REPO / ".exit_codes_doctored.md"
        try:
            tmp.write_text(doctored, encoding="utf-8")
            result = _run(tmp)
            assert result.returncode != 0, (
                "表里的码是错的,核对器却报通过 —— 它没在看那张表"
            )
            assert "退出码" in (result.stdout + result.stderr)
        finally:
            tmp.unlink(missing_ok=True)

    def test_missing_dependency_is_not_reported_as_a_code_mismatch(self):
        """命令没跑起来要说"环境缺依赖",不能说"退出码与表对不上"

        两件事混在一起,会把环境的毛病说成行为不符 —— 那会让真正的问题
        淹没在错误的说法里。
        """
        import check_exit_codes as checker

        assert checker.looks_like_missing_dependency(
            "ModuleNotFoundError: No module named 'pandas'"
        )
        assert checker.looks_like_missing_dependency(
            "/usr/bin/python3: No module named forgemind.cli"
        )
        assert not checker.looks_like_missing_dependency(
            "❌ 未知策略 NoSuchStrategyAnywhere"
        )
        assert not checker.looks_like_missing_dependency("")

    def test_it_catches_a_missing_row(self):
        """表里少了一行,它也得报出来"""
        text = (REPO / "README.md").read_text(encoding="utf-8")
        doctored = re.sub(r"^\| 130 \| 用户中断.*\n", "", text, flags=re.M)
        assert doctored != text, "没删掉 README 的行,这条断言就落空了"
        tmp = REPO / ".exit_codes_missing.md"
        try:
            tmp.write_text(doctored, encoding="utf-8")
            result = _run(tmp)
            assert result.returncode != 0, "表里少了码,核对器却报通过"
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
