# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""发布版本号的判据:post 号接续、基础版本变了就重新计数、打进四处声明。

版本号算错的后果是"用户装不到新的构建",而且表面看不出来 —— pip 只是
说 "Requirement already satisfied" ✓。

打补丁的那一份是**构建用的源码副本**,不是仓库里的源码 ✓:仓库里的四处
声明保持原样 ✓,那是维护者抬大版本的地方 ✓。
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from apply_publish_version import apply_version  # noqa: E402
from publish_version import next_version, split_post  # noqa: E402


class TestSplitPost:
    """版本号里的 post 部分。"""

    def test_post_version_is_split(self):
        assert split_post("2026.9.3.post2") == ("2026.9.3", 2)

    def test_plain_version_has_no_post(self):
        assert split_post("2026.9.3") == ("2026.9.3", 0)

    def test_empty_version(self):
        assert split_post("") == ("", 0)


class TestNextVersion:
    """下一次发布的版本号。"""

    def test_first_publish_gets_post_one(self):
        assert next_version("2026.9.3", "") == "2026.9.3.post1"

    def test_post_number_continues(self):
        assert next_version("2026.9.3", "2026.9.3.post1") == "2026.9.3.post2"

    def test_post_number_continues_across_many_publishes(self):
        assert next_version("2026.9.3", "2026.9.3.post17") == "2026.9.3.post18"

    def test_new_base_version_restarts_the_counter(self):
        """维护者抬了大版本,post 号从头开始。"""
        assert next_version("2026.10.0", "2026.9.3.post9") == "2026.10.0.post1"

    def test_publish_after_a_plain_version(self):
        """上一次发的是基础版本本身,这一次接 post1。"""
        assert next_version("2026.9.3", "2026.9.3") == "2026.9.3.post1"

    def test_empty_base_is_rejected(self):
        try:
            next_version("", "2026.9.3.post1")
        except ValueError:
            return
        raise AssertionError("空的基础版本必须报错")


class TestApplyVersion:
    """把版本号打进构建用的源码副本。"""

    def _copy_tree(self, tmp_path: Path) -> Path:
        """造一份只含版本声明的最小源码树。"""
        (tmp_path / "forgemind").mkdir(parents=True)
        (tmp_path / "forgemind-ui" / "src-tauri").mkdir(parents=True)
        (tmp_path / "pyproject.toml").write_text('version = "2026.9.3"\n', encoding="utf-8")
        (tmp_path / "forgemind" / "__init__.py").write_text(
            '__version__ = "2026.9.3"\n', encoding="utf-8"
        )
        (tmp_path / "forgemind-ui" / "src-tauri" / "Cargo.toml").write_text(
            '[package]\nversion = "2026.9.3"\n', encoding="utf-8"
        )
        (tmp_path / "forgemind-ui" / "package.json").write_text(
            '{\n  "version": "2026.9.3",\n}\n', encoding="utf-8"
        )
        return tmp_path

    def test_all_four_declarations_are_updated(self, tmp_path):
        root = self._copy_tree(tmp_path)
        changed = apply_version(root, "2026.9.3.post1")
        assert len(changed) == 4, f"四处版本声明都要改,实际改了 {changed}"
        assert 'version = "2026.9.3.post1"' in (root / "pyproject.toml").read_text()
        assert '__version__ = "2026.9.3.post1"' in (root / "forgemind" / "__init__.py").read_text()
        assert (
            'version = "2026.9.3.post1"'
            in (root / "forgemind-ui" / "src-tauri" / "Cargo.toml").read_text()
        )
        assert '"version": "2026.9.3.post1"' in (root / "forgemind-ui" / "package.json").read_text()

    def test_cargo_dependency_versions_are_not_touched(self, tmp_path):
        """Cargo.toml 里依赖也有 version 行 —— 只能改包自己的那一处。"""
        root = self._copy_tree(tmp_path)
        cargo = root / "forgemind-ui" / "src-tauri" / "Cargo.toml"
        cargo.write_text(
            '[package]\nversion = "2026.9.3"\n\n[dependencies]\nserde = { version = "1.0" }\n',
            encoding="utf-8",
        )
        apply_version(root, "2026.9.3.post1")
        text = cargo.read_text(encoding="utf-8")
        assert 'version = "2026.9.3.post1"' in text
        assert 'version = "1.0"' in text, "依赖的版本不能被改"

    def test_missing_declaration_is_an_error(self, tmp_path):
        root = self._copy_tree(tmp_path)
        (root / "pyproject.toml").unlink()
        try:
            apply_version(root, "2026.9.3.post1")
        except SystemExit:
            return
        raise AssertionError("缺了版本声明必须报错,不能静默放过")


class TestSourceDeclarationUnchanged:
    """仓库里的四处声明不该被发布流程改动。"""

    def test_repository_still_declares_the_base_version(self):
        pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
        init = (REPO / "forgemind" / "__init__.py").read_text(encoding="utf-8")
        cargo = (REPO / "forgemind-ui" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
        package = (REPO / "forgemind-ui" / "package.json").read_text(encoding="utf-8")
        versions = {
            "pyproject": pyproject.split('version = "', 1)[1].split('"', 1)[0],
            "init": init.split('__version__ = "', 1)[1].split('"', 1)[0],
            "cargo": cargo.split('version = "', 1)[1].split('"', 1)[0],
            "package": package.split('"version": "', 1)[1].split('"', 1)[0],
        }
        assert len(set(versions.values())) == 1, f"四处版本声明不一致: {versions}"
        assert ".post" not in versions["pyproject"], "仓库里声明的是基础版本,不是发布版本"
