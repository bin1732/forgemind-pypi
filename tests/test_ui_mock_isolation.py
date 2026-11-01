# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""界面 mock 隔离检查的双向验证。

检查器最怕两种坏法:永远通过(假绿)和永远报警(假红)。这里用合成样本
双向验证 —— 会命中的样本必须报警,干净的样本必须不报警;再对真实界面
目录跑一遍,确认现在的仓库站在干净的那一侧。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from check_ui_mock_isolation import check  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clean_tree(tmp_path: Path) -> Path:
    """一个干净的界面目录:mock 只被 jest 配置引用。"""
    ui = tmp_path / "ui"
    _write(ui / "__mocks__" / "styleMock.js", "module.exports = {};\n")
    _write(ui / "jest.config.js",
           "module.exports = { moduleNameMapper: {"
           '"\\\\.(css)$": "<rootDir>/__mocks__/styleMock.js" } };\n')
    _write(ui / "next.config.js", "module.exports = {};\n")
    _write(ui / "components" / "Panel.tsx", "export const Panel = () => null;\n")
    return ui


class TestMockIsolationChecker:
    def test_clean_tree_passes(self, tmp_path):
        assert check(_clean_tree(tmp_path)) == []

    def test_build_config_referencing_mock_is_caught(self, tmp_path):
        ui = _clean_tree(tmp_path)
        _write(ui / "next.config.js",
               "module.exports = { webpack: (c) => { c.resolve.alias = "
               '{"x": "<rootDir>/__mocks__/styleMock.js"}; return c; } };\n')
        problems = check(ui)
        assert problems, "next.config 引用 mock 却没报警"
        assert any("next.config.js" in p for p in problems), problems

    def test_source_importing_mock_is_caught(self, tmp_path):
        ui = _clean_tree(tmp_path)
        _write(ui / "components" / "Panel.tsx",
               'import mock from "../__mocks__/styleMock";\n')
        problems = check(ui)
        assert problems, "业务源码 import mock 却没报警"
        assert any("Panel.tsx" in p for p in problems), problems

    def test_test_file_may_reference_mock(self, tmp_path):
        ui = _clean_tree(tmp_path)
        _write(ui / "components" / "__tests__" / "Panel.test.tsx",
               'import mock from "../../__mocks__/styleMock";\n')
        assert check(ui) == [], "测试文件引用 mock 不该报警"

    def test_build_output_is_ignored(self, tmp_path):
        """构建产物里的引用不算违规 —— 那是生成物,不是源码"""
        ui = _clean_tree(tmp_path)
        _write(ui / "out" / "Panel.js", 'import x from "../__mocks__/a";\n')
        assert check(ui) == [], "构建产物不该被当成源码"

    def test_real_ui_directory_is_clean(self):
        ui = REPO / "forgemind-ui"
        if not ui.is_dir():
            pytest.skip("这个仓里没有界面目录")
        assert check(ui) == []
