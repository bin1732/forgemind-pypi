# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""界面数据来源核对器自己得可靠。

它盯的是组件里有没有写死在那儿的指标值。这个错很隐蔽:界面看着正常,
后端早就已经不返回这些数了。

所以它不能有两个毛病:

- 漏报:组件里写死了数,它却没报。
- 误报:把第三方依赖与构建产物里的常量当成我们写的 —— 那会让检查在
  装了依赖之后恒红,真问题反被淹掉。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_ui_data_driven as checker  # noqa: E402


def _write(path: pathlib.Path, body: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class TestHardcodedValues:
    def test_our_component_is_reported(self, tmp_path):
        """我们自己的组件里写死了数,要报出来"""
        _write(tmp_path / "components" / "panel.tsx", "const sharpe = 1.2345;\n")
        problems, files = checker.check_tree(tmp_path)
        assert files == 1, files
        assert problems, "组件里写死在那儿的指标值没被报出来"

    def test_third_party_is_not_reported(self, tmp_path):
        """node_modules 里的常量不是我们写的,不报"""
        _write(tmp_path / "node_modules" / "pkg" / "x.ts", "const coverage = 1.2345;\n")
        problems, files = checker.check_tree(tmp_path)
        assert files == 0, files
        assert problems == []

    def test_build_output_is_not_reported(self, tmp_path):
        """.next 里的产物也不报"""
        _write(tmp_path / ".next" / "y.ts", "const ratio = 3.4567;\n")
        problems, files = checker.check_tree(tmp_path)
        assert files == 0, files
        assert problems == []

    def test_test_files_are_not_reported(self, tmp_path):
        """测试文件里的数字是断言的一部分,不是界面上的写死值"""
        _write(
            tmp_path / "components" / "__tests__" / "panel.test.tsx",
            "expect(1.2345).toBe(1.2345);\n",
        )
        problems, files = checker.check_tree(tmp_path)
        assert files == 0, files
        assert problems == []

    def test_our_component_next_to_third_party_is_still_reported(self, tmp_path):
        """装了依赖也不能让真问题被淹掉"""
        _write(tmp_path / "node_modules" / "pkg" / "x.ts", "const coverage = 1.2345;\n")
        _write(tmp_path / "components" / "panel.tsx", "const sharpe = 2.3456;\n")
        problems, files = checker.check_tree(tmp_path)
        assert files == 1, files
        assert len(problems) == 1, problems
        assert "panel.tsx" in problems[0]


class TestInventedAccount:
    """界面替用户编一个账户 —— 后端照着算,结论看着正常,依据是假的。"""

    def test_integer_cash_is_reported(self, tmp_path):
        """整数写死的现金躲过了浮点那条规则,这里要抓住它。"""
        _write(
            tmp_path / "components" / "palette.tsx",
            "const args = { symbol, cash: 100000, total_equity: 200000 };\n",
        )
        problems, files = checker.check_tree(tmp_path)
        assert files == 1, files
        assert problems, "写死的账户没被报出来"

    def test_held_position_is_reported(self, tmp_path):
        _write(
            tmp_path / "components" / "palette.tsx",
            "const args = { positions: [{ symbol, quantity: 100, avg_price: 1500 }] };\n",
        )
        problems, _ = checker.check_tree(tmp_path)
        assert problems, "写死的持仓没被报出来"

    def test_real_value_is_not_reported(self, tmp_path):
        """值来自状态,不是字面量 —— 不该报。"""
        _write(
            tmp_path / "components" / "palette.tsx",
            "const args = { symbol, cash: state.cash, positions: state.portfolio };\n",
        )
        problems, _ = checker.check_tree(tmp_path)
        assert problems == [], problems

    def test_ordinary_words_do_not_hide_the_line(self, tmp_path):
        """普通词里的 s / em / ms 不该把整行判成样式行。

        "args"、"positions"、"system" 结尾或中间都有这些字母。之前
        一行里出现它们,那一行写死什么都不报 —— 检查器还是绿的。
        """
        _write(
            tmp_path / "components" / "palette.tsx",
            "const args = { system, cash: 100000 };\n",
        )
        problems, _ = checker.check_tree(tmp_path)
        assert problems, "整行被普通词盖住了,写死的数据没被发现"

    def test_threshold_is_not_reported(self, tmp_path):
        """比较表达式里的常量是界面规则,不是显示值。"""
        _write(
            tmp_path / "components" / "grid.tsx",
            "const cls = Math.abs(ic) >= 0.02 ? 'strong' : 'weak';\n",
        )
        problems, _ = checker.check_tree(tmp_path)
        assert problems == [], problems


class TestRealUiIsClean:
    def test_repository_ui_has_no_hardcoded_metrics(self):
        problems, files = checker.check_tree(REPO / "forgemind-ui")
        assert not problems, problems
        assert files > 0, "一个文件都没扫到,这条断言就没有意义"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
