# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""关卡表要**双向**核对:表里有的都得存在,存在的都得在表里。

正向的核对(表里有的都有对应的流水线作业)早就有了,但反向的没有 ——
于是 README 那张表只列了 6 道,仓里实际有 20 个机器验证作业,读者以为
关卡就那么多。

反向缺口比正向隐蔽:正向缺了会报红,反向缺了只是"少说" —— 而在承诺型
文档里,"少说"同样是误导。

所以这里用**造出来的**流水线目录双向验规则本身:该报的报、不该报的不
报,不能靠"当前这仓碰巧合规"来证明。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_readme_gates as gates  # noqa: E402


def _workflow(dirpath: Path, name: str, jobs: dict) -> None:
    import yaml

    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / name).write_text(
        yaml.safe_dump({"jobs": jobs}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


class TestMissingFromTable:
    def test_a_job_not_named_is_reported(self, tmp_path):
        wf = tmp_path / ".github" / "workflows"
        _workflow(wf, "ci-x.yml", {"lint": {"name": "Code Quality"}})
        problems = gates.missing_from_table({("ci-x.yml", "别的作业")}, wf)
        assert problems, "没被点名的作业没被报出来"
        assert "Code Quality" in problems[0], problems

    def test_a_named_job_passes(self, tmp_path):
        wf = tmp_path / ".github" / "workflows"
        _workflow(wf, "ci-x.yml", {"lint": {"name": "Code Quality"}})
        problems = gates.missing_from_table({("ci-x.yml", "Code Quality")}, wf)
        assert problems == [], problems

    def test_the_job_key_also_counts(self, tmp_path):
        """作业没写 name 时用 key —— 两种写法都要认。"""
        wf = tmp_path / ".github" / "workflows"
        _workflow(wf, "ci-x.yml", {"lint": {}})
        assert gates.missing_from_table({("ci-x.yml", "lint")}, wf) == []
        assert gates.missing_from_table(set(), wf) != []

    def test_exempt_jobs_are_not_reported(self, tmp_path):
        """发布流水线自己的步骤是对外承诺之外的东西。"""
        wf = tmp_path / ".github" / "workflows"
        _workflow(wf, "ship.yml", {"ship": {"name": "ship"}})
        assert gates.missing_from_table(set(), wf) == []


class TestRealRepo:
    def test_the_checker_passes_on_this_repository(self):
        """判据在本仓上要通过 —— 它自己坏了要说出来。"""
        readme = REPO / "README.md"
        if not readme.is_file():
            return
        import yaml

        text = readme.read_text(encoding="utf-8")
        rows = gates.GATE_ROW.findall(text)
        listed = {(w, j.strip()) for w, j in rows}
        problems = gates.missing_from_table(listed, REPO / ".github" / "workflows")
        assert problems == [], problems
        assert rows, "README 里的关卡表没匹配到行"
        yaml.safe_load("a: 1")
