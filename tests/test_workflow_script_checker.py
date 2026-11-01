# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""工作流脚本检查器:三类判据都要拿合成样本双向验证。

检查器自己错了,门禁就成了摆设 —— 而门禁的判据一旦宽松,红与绿都不再
说明问题。这里把三类判据各钉住一个方向,再加一个反向样本:

- 工作目录在本地不存在 → 只能记"没查",不能报"脚本缺失"。镜像工作流要
  把私人源码 checkout 到 src/,本地没 checkout 过;把"查不到"当成"没有",
  会让检查在本地恒红,真问题反被淹掉。
- 工作目录在、脚本不在 → 必须报出来。
- 工作目录在、脚本也在 → 不许报。
- 脚本引号写坏 → shell 自己的语法检查必须报出来;写对 → 不许报。
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_workflow_scripts as cws  # noqa: E402


class TestScriptExistsVerification:
    """脚本存在性检查:能不能核对,与核对出来是什么,是两回事"""

    def test_absent_workdir_is_unverified_not_missing(self, tmp_path):
        """工作目录不在 → 不报缺失,只记没查"""
        problems, unverified = cws.check_script_exists(
            "标签", "python scripts/check_thing.py", str(tmp_path / "absent"), tmp_path
        )
        assert problems == [], "无法核对时不能报成缺失"
        assert unverified == 1, "无法核对的条数要记下来"

    def test_present_workdir_with_missing_script_is_reported(self, tmp_path):
        """工作目录在、脚本不在 → 必须报出来"""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "other.py").write_text("", encoding="utf-8")
        problems, unverified = cws.check_script_exists(
            "标签", "python scripts/check_thing.py", str(tmp_path), tmp_path
        )
        assert unverified == 0
        assert len(problems) == 1, f"缺失的脚本没被报出来: {problems}"
        assert "check_thing.py" in problems[0]

    def test_present_script_is_not_reported(self, tmp_path):
        """工作目录在、脚本也在 → 不许报"""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check_thing.py").write_text("", encoding="utf-8")
        problems, unverified = cws.check_script_exists(
            "标签", "python scripts/check_thing.py", str(tmp_path), tmp_path
        )
        assert problems == []
        assert unverified == 0


class TestShellSyntax:
    """shell 语法检查:引号写坏必须被抓"""

    def test_unterminated_quote_is_caught(self):
        problems = cws.check_shell_syntax("标签", '{\n  echo "### 标题\n  echo ""\n}\n')
        assert problems, "引号没闭合必须报出来"
        assert "语法" in problems[0]

    def test_valid_script_is_not_reported(self):
        assert (
            cws.check_shell_syntax("标签", '{\n  echo "### 标题"\n  echo ""\n}\n') == []
        )

    def test_broken_script_is_caught_through_check_run(self):
        """check_run 也要把语法问题带出来(它是对外的入口)"""
        problems = cws.check_run("标签", '{\n  echo "### 标题\n  echo ""\n}\n')
        assert any("语法" in item for item in problems), problems


class TestJobGraph:
    """作业之间的引用:指向不存在的东西,会让整个工作流不被执行"""

    @staticmethod
    def _repo(tmp_path: Path, body: str) -> Path:
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "demo.yml").write_text(body, encoding="utf-8")
        return tmp_path

    def test_missing_needs_is_reported(self, tmp_path, capsys):
        """needs 指向不存在的作业 → 必须报出来"""
        repo = self._repo(
            tmp_path,
            "name: demo\n"
            "on: workflow_dispatch\n"
            "jobs:\n"
            "  a:\n"
            "    needs: 不存在的作业\n"
            "    runs-on: ubuntu-26.04\n"
            "    steps:\n"
            "      - run: echo hi\n",
        )
        assert cws.main(repo) == 1
        assert "不存在" in capsys.readouterr().out

    def test_missing_local_action_is_reported(self, tmp_path, capsys):
        """引用的本地 action 不在仓里 → 必须报出来"""
        repo = self._repo(
            tmp_path,
            "name: demo\n"
            "on: workflow_dispatch\n"
            "jobs:\n"
            "  a:\n"
            "    runs-on: ubuntu-26.04\n"
            "    steps:\n"
            "      - uses: ./.github/actions/没有这个action\n",
        )
        assert cws.main(repo) == 1
        assert "本地 action" in capsys.readouterr().out

    def test_dependency_cycle_is_reported(self, tmp_path, capsys):
        """作业依赖成环 → 必须报出来"""
        repo = self._repo(
            tmp_path,
            "name: demo\n"
            "on: workflow_dispatch\n"
            "jobs:\n"
            "  a:\n"
            "    needs: b\n"
            "    runs-on: ubuntu-26.04\n"
            "    steps:\n"
            "      - run: echo a\n"
            "  b:\n"
            "    needs: a\n"
            "    runs-on: ubuntu-26.04\n"
            "    steps:\n"
            "      - run: echo b\n",
        )
        assert cws.main(repo) == 1
        assert "成环" in capsys.readouterr().out

    def test_sound_workflow_passes(self, tmp_path, capsys):
        """引用都指得到 → 不许报"""
        repo = self._repo(
            tmp_path,
            "name: demo\n"
            "on: workflow_dispatch\n"
            "jobs:\n"
            "  a:\n"
            "    runs-on: ubuntu-26.04\n"
            "    steps:\n"
            "      - run: echo a\n"
            "  b:\n"
            "    needs: a\n"
            "    runs-on: ubuntu-26.04\n"
            "    steps:\n"
            "      - run: echo b\n",
        )
        assert cws.main(repo) == 0


class TestWorkingDirectorySemantics:
    """工作目录的拼法要按 GitHub 的真实语义:步骤级覆盖作业默认"""

    def test_step_working_directory_overrides_job_default(self, tmp_path):
        """步骤上的 working-directory 是覆盖,不是拼接"""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "x.py").write_text("", encoding="utf-8")
        (tmp_path / "jobdir").mkdir()
        (tmp_path / "jobdir" / "scripts").mkdir()
        (tmp_path / "jobdir" / "scripts" / "y.py").write_text("", encoding="utf-8")
        # 工作目录是 jobdir,脚本写 scripts/y.py → 找得到
        problems, _ = cws.check_script_exists(
            "标签", "python scripts/y.py", "jobdir", tmp_path
        )
        assert problems == [], problems
        # 工作目录是 "."(覆盖),脚本写 scripts/x.py → 也找得到
        problems, _ = cws.check_script_exists(
            "标签", "python scripts/x.py", ".", tmp_path
        )
        assert problems == [], problems

    def test_parent_relative_script_is_verified(self, tmp_path):
        """../scripts/x.py 这种写法要能核对,而不是直接跳过"""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "x.py").write_text("", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        problems, _ = cws.check_script_exists(
            "标签", "python ../scripts/x.py", "sub", tmp_path
        )
        assert problems == [], problems
        problems, _ = cws.check_script_exists(
            "标签", "python ../scripts/没有这个.py", "sub", tmp_path
        )
        assert len(problems) == 1, problems
