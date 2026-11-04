# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""工作流脚本检查器:三类判据都要拿合成样本双向验证。

检查器自己错了,门禁就成了摆设 —— 而门禁的判据一旦宽松,红与绿都不再
说明问题。这里把三类判据各钉住一个方向,再加一个反向样本:

- 工作目录在本地不存在 → 只能记"没查",不能报"脚本缺失"。有些作业把
  源码 checkout 到别处,本地没 checkout 过;把"查不到"当成"没有",
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
            "      - uses: actions/checkout@v7\n"
            "      - run: echo a\n"
            "  b:\n"
            "    needs: a\n"
            "    runs-on: ubuntu-26.04\n"
            "    steps:\n"
            "      - uses: actions/checkout@v7\n"
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


class TestPublishTriggerIsBranchLimited:
    """发布那条工作流的 push 触发必须限定分支"""

    def _workflow(self, push_block: str) -> dict:
        return {
            "on": {"push": push_block},
            "permissions": {"contents": "write"},
            "jobs": {"ship": {"runs-on": "ubuntu-26.04", "steps": []}},
        }

    def test_missing_branch_filter_is_reported(self, tmp_path):
        """没有分支过滤要报出来 —— 推到任何分支都会发布"""
        path = tmp_path / "ship.yml"
        problems = cws.check_publish_trigger_is_branch_limited(
            path, self._workflow({"paths-ignore": ["releases/**"]})
        )
        assert len(problems) == 1, problems
        assert "分支" in problems[0]

    def test_branch_filter_is_accepted(self, tmp_path):
        """有限定分支就不报"""
        path = tmp_path / "ship.yml"
        problems = cws.check_publish_trigger_is_branch_limited(
            path, self._workflow({"branches": ["main"], "paths-ignore": ["releases/**"]})
        )
        assert problems == [], problems

    def test_workflow_without_write_permission_is_not_judged(self, tmp_path):
        """只读的工作流(校验类)用不着限定分支"""
        path = tmp_path / "ci-lint.yml"
        data = self._workflow({"paths-ignore": ["releases/**"]})
        data["permissions"] = {"contents": "read"}
        problems = cws.check_publish_trigger_is_branch_limited(path, data)
        assert problems == [], problems

    def test_repository_workflows_satisfy_the_rule(self):
        """仓里的发布工作流真的要限定了"""
        import yaml

        root = Path(__file__).resolve().parent.parent / ".github/workflows"
        for path in sorted(root.glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            problems = cws.check_publish_trigger_is_branch_limited(path, data)
            assert problems == [], f"{path.name}: {problems}"


class TestConcurrencyGroupsAreNotShared:
    """两个工作流共用一个并发组,必然有一个被取消"""

    def test_shared_group_is_reported(self):
        """共用一组 → 必须报出来"""
        problems = cws.check_concurrency_groups_are_not_shared(
            [("verify.yml", "post-ship-${{ github.ref }}"),
             ("verify-live.yml", "post-ship-${{ github.ref }}")]
        )
        assert len(problems) == 1, problems
        assert "verify.yml" in problems[0] and "verify-live.yml" in problems[0]

    def test_distinct_groups_are_not_reported(self):
        """各用各的组 → 不许报"""
        problems = cws.check_concurrency_groups_are_not_shared(
            [("verify.yml", "verify-${{ github.ref }}"),
             ("verify-live.yml", "verify-live-${{ github.ref }}")]
        )
        assert problems == [], problems

    def test_same_literal_prefix_is_reported(self):
        """字面前缀相同 → 运行时可能落进同一组,必须报出来"""
        problems = cws.check_concurrency_groups_are_not_shared(
            [("verify.yml", "post-ship-${{ github.ref }}"),
             ("verify-live.yml", "post-ship-${{ github.ref_name }}")]
        )
        assert len(problems) == 1, problems
        assert "前缀" in problems[0]

    def test_prefix_helper(self):
        """前缀取的是第一个表达式之前的字面量"""
        assert cws.concurrency_group_prefix("verify-${{ github.ref }}") == "verify-"
        assert cws.concurrency_group_prefix("plain-group") == "plain-group"
        assert cws.concurrency_group_prefix("${{ github.ref }}") == ""

    def test_single_workflow_with_group_is_not_reported(self):
        """只有一个工作流声明了组 → 不许报"""
        problems = cws.check_concurrency_groups_are_not_shared(
            [("ship.yml", "ship-${{ github.ref }}")]
        )
        assert problems == [], problems

    def test_workflow_without_concurrency_block_has_no_group(self):
        """没声明并发组 → 取不到组,不参与判据"""
        assert cws.collect_concurrency_group({"jobs": {}}) is None
        assert cws.collect_concurrency_group({"concurrency": {}}) is None
        assert cws.collect_concurrency_group({"concurrency": {"group": "  "}}) is None
        assert cws.collect_concurrency_group({"concurrency": {"group": "x"}}) == "x"

    def test_repository_workflows_use_distinct_groups(self):
        """仓里的工作流真的各用各的组"""
        import yaml

        root = Path(__file__).resolve().parent.parent / ".github/workflows"
        groups = []
        for path in sorted(root.glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            group = cws.collect_concurrency_group(data)
            if group is not None:
                groups.append((path.name, group))
        problems = cws.check_concurrency_groups_are_not_shared(groups)
        assert problems == [], problems

    def test_the_three_post_publish_verifications_are_separate(self):
        """三个发布后验证必须各有各的并发组 —— 这正是被取消过的那个坑"""
        import yaml

        root = Path(__file__).resolve().parent.parent / ".github/workflows"
        post_publish = []
        for name in ("verify.yml", "verify-live.yml", "verify-desktop.yml"):
            data = yaml.safe_load((root / name).read_text(encoding="utf-8"))
            # YAML 1.1 把键 on 解析成布尔 True,所以两种写法都得试。
            on = data.get("on")
            if not isinstance(on, dict):
                on = data.get(True) if isinstance(data.get(True), dict) else {}
            if "workflow_run" in on:
                post_publish.append((name, cws.collect_concurrency_group(data)))
        assert len(post_publish) == 3, f"发布后验证的工作流数不对: {post_publish}"
        for name, group in post_publish:
            assert group, f"{name} 没有声明并发组"
        groups = [g for _, g in post_publish]
        assert len(set(groups)) == len(groups), f"这几个工作流共用并发组: {post_publish}"
