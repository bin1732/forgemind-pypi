# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""检查器接线检查:脚本写好放着没人调用,等于一道门禁都没有。

这里盯三件事:

- 仓里的检查器脚本,工作流里得真的调用它。
- **只在注释里提到不算** —— 那是解释,不是执行。少了这一层,把
  require 那一行删掉、注释还在,检查器照样说"接上了",而那道门禁
  已经不设防了。
- 判据文件(.js)也算数:发布前那道关的判据是 JS,把它从工作流里摘掉
  同样要被抓到。
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_gates_wired as gw  # noqa: E402


def _repo(tmp_path: pathlib.Path, scripts: list[str], workflows: dict[str, str]) -> pathlib.Path:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    for name in scripts:
        (root / "scripts" / name).write_text("# script\n", encoding="utf-8")
    # 检查器自己也在仓里 —— 它检查的就是自己所在的这个仓
    (root / "scripts" / "check_gates_wired.py").write_text(
        (REPO / "scripts" / "check_gates_wired.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for name, body in workflows.items():
        # 真实仓里检查器自己是被调用的(ci-lint 那一档)。临时仓照抄这个
        # 布局,不然它会先把自己报成"没被调用"。
        body = body + (
            "      - run: python scripts/check_gates_wired.py\n"
        )
        (root / ".github" / "workflows" / name).write_text(body, encoding="utf-8")
    return root


class TestScriptMustBeCalled:
    def test_uncalled_script_is_reported(self, tmp_path):
        root = _repo(tmp_path, ["check_thing.py"], {"ci.yml": "name: ci\n"})
        proc = subprocess.run(
            [sys.executable, str(root / "scripts" / "check_gates_wired.py"),
             "--public", str(root)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "check_thing.py" in proc.stderr

    def test_called_script_is_not_reported(self, tmp_path):
        root = _repo(
            tmp_path,
            ["check_thing.py"],
            {"ci.yml": "name: ci\njobs:\n  a:\n    steps:\n"
                       "      - run: python scripts/check_thing.py\n"},
        )
        proc = subprocess.run(
            [sys.executable, str(root / "scripts" / "check_gates_wired.py"),
             "--public", str(root)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_comment_only_mention_is_not_a_call(self, tmp_path):
        """注释里提到脚本名 ≠ 被调用 —— 少了这一层,门禁会悄悄不设防"""
        root = _repo(
            tmp_path,
            ["gate_check.js"],
            {"ship.yml": "name: ship\njobs:\n  a:\n    steps:\n"
                         "      - run: |\n"
                         "          # 判据在 scripts/gate_check.js,能被单独验\n"
                         "          echo 没有真的调用\n"},
        )
        proc = subprocess.run(
            [sys.executable, str(root / "scripts" / "check_gates_wired.py"),
             "--public", str(root)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "gate_check.js" in proc.stderr


class TestRealRepo:
    def test_repository_checkers_are_all_wired(self):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "check_gates_wired.py"),
             "--public", str(REPO)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
