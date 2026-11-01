# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""端到端流水线的结果表格:对齐、版本真实、动态列表在框内。"""

from __future__ import annotations

import pytest

from forgemind.core.pipeline.end_to_end import (
    PipelineResult,
    _display_width,
    _render_box,
)


def _result(**overrides) -> PipelineResult:
    """构造一个内容齐全的结果,便于检查表格。"""
    base = dict(
        n_symbols=5,
        n_days=120,
        n_bars=600,
        n_factors_computed=42,
        ic_top_factors=[
            {"factor": "momentum_20d", "ic_mean": 0.0832, "rank_ic_mean": 0.0911},
            {"factor": "value_bp", "ic_mean": -0.0412, "rank_ic_mean": -0.0388},
        ],
        best_ic_mean=0.0832,
        best_icir=1.42,
        model_name="LightGBM",
        model_backend="lightgbm",
        cv_rank_ic_mean=0.0512,
        cv_rank_ic_std=0.0091,
        cv_sharpe=1.18,
        model_found_signal=True,
        top_features={"momentum_20d": 0.31, "value_bp": 0.22},
        total_return=0.1876,
        sharpe=1.42,
        sortino=1.95,
        max_drawdown=-0.0832,
        win_rate=0.5714,
        n_trades=42,
        data_source="akshare",
        start_date="2024-01-01",
        end_date="2024-04-30",
        signals=[
            {
                "symbol": "600519.SH",
                "side": "BUY",
                "confidence": 0.78,
                "rationale": "动量与价值因子同向,回撤可控",
            }
        ],
        duration_seconds=12.34,
    )
    base.update(overrides)
    return PipelineResult(**base)


class TestBoxAlignment:
    def test_every_row_has_the_same_display_width(self):
        """框内每一行的显示宽度都相同,右边框才对得齐。"""
        text = _result().summary()
        widths = {
            _display_width(line)
            for line in text.splitlines()
            if line.startswith("║")
        }
        assert len(widths) == 1, f"框内行的宽度不一致: {sorted(widths)}"

    def test_top_and_bottom_borders_match_the_rows(self):
        """上下边框的宽度与框内行一致。"""
        lines = _result().summary().splitlines()
        row_width = _display_width(lines[1])
        assert _display_width(lines[0]) == row_width
        assert _display_width(lines[-1]) == row_width

    def test_every_line_is_inside_the_frame(self):
        """因子、特征、信号这些动态行也要在框内,不能漏到框外。"""
        text = _result().summary()
        for line in text.splitlines():
            assert line.startswith(("╔", "╠", "╚", "║")), f"有行漏在框外: {line!r}"


class TestVersionIsReal:
    def test_title_shows_the_installed_version(self):
        """标题里的版本号是包的真实版本,不是某个历史编号。"""
        import forgemind

        text = _result().summary()
        assert f"v{forgemind.__version__}" in text

    def test_version_is_not_a_hardcoded_release_series(self):
        """版本号不能是手写的历史发布编号。"""
        import forgemind

        text = _result().summary()
        assert "v2026.09" not in text, "标题里出现了与包版本无关的历史编号"


class TestRenderBox:
    def test_separator_row(self):
        """None 表示画分隔线。"""
        text = _render_box(["一", None, "二"])
        lines = text.splitlines()
        assert lines[0].startswith("╔")
        assert lines[2].startswith("╠")
        assert lines[-1].startswith("╚")

    def test_cjk_characters_count_as_two_columns(self):
        """中文占两列,算宽度时按两列算。"""
        assert _display_width("中文") == 4
        assert _display_width("ab") == 2

    def test_empty_row(self):
        """空行也能对齐。"""
        text = _render_box(["", "x"])
        widths = {
            _display_width(line)
            for line in text.splitlines()
            if line.startswith("║")
        }
        assert len(widths) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
