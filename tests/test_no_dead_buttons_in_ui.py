# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
桌面端几个按钮是死按钮(纯 setState / 纯 alert),用户按下去没真后端动作。

底层修法:所有按钮必须接通真后端,或者诚实标 disabled + 提示。

本测试:
- strategy-panel "+ 新建" 按钮 onClick 必须调 runPipeline
- kline-chart 1d timeframe 按钮 enabled, 1m/5m/15m/1h disabled
- 严禁 timeframe 按钮全是 enabled + 无 onClick
"""
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
KLINE = REPO / "forgemind-ui" / "components" / "kline-chart.tsx"
STRATEGY = REPO / "forgemind-ui" / "components" / "strategy-panel.tsx"


def test_strategy_panel_new_button_calls_run_pipeline():
    """+ 新建 按钮不能只 setPipelineRunning(true),必须接通 runPipeline"""
    src = STRATEGY.read_text(encoding="utf-8")
    # 找含 runPipeline 的 onClick
    onclick = re.search(r"onClick=\{[^}]*runPipeline[^}]*\}", src)
    assert onclick, (
        "strategy-panel 没找到调 runPipeline 的 onClick;"
        " + 新建 按钮曾是死动作(setPipelineRunning(true) 只切 flag)"
    )


def test_kline_chart_timeframe_1d_active_others_disabled():
    """1m/5m/15m/1h 必须 disabled(数据源仅日线),1d 才是 enabled"""
    src = KLINE.read_text(encoding="utf-8")
    for tf in ["1m", "5m", "15m", "1h"]:
        pat = rf'tf:\s*"{tf}".*?enabled:\s*false'
        assert re.search(pat, src, re.DOTALL), (
            f"kline-chart {tf} 应该 enabled: false(数据源仅日线)"
        )
    assert re.search(r'tf:\s*"1d".*?enabled:\s*true', src, re.DOTALL), (
        "kline-chart 1d 应该 enabled: true(真实日线)"
    )


def test_kline_chart_timeframe_label_is_daily():
    """K 线顶部标签必须诚实显示"日线",不再写"5m"等不可能的周期"""
    src = KLINE.read_text(encoding="utf-8")
    assert "K 线 · 1d" in src, "kline-chart 顶部标签应显示 K 线 · 1d(日线)"
    assert "K 线 · 5m" not in src, (
        "kline-chart 顶部仍写 K 线 · 5m — 但 DuckDB kline_daily 是日线,"
        " 5m 物理上拿不到"
    )
