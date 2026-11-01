# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
portfolio-panel 之前用 portfolio.current_price 算 PnL,但 current_price 是
agent snapshot 落盘时的均价占位(API 不返回当前价),unrealized PnL 永远是 0。

底层修法:KLineChart 拉真实 K 线成功后,把最后 close 写到
useAppStore().currentPrices[symbol];portfolio-panel 优先用 currentPrices
里的真现价,没拉到时显式标 "—(等 K 线)" 而不是用均价顶。

回归测试:防止 portfolio-panel 又走回"current_price 用均价占位"的旧实现。
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PANEL = REPO / "forgemind-ui" / "components" / "portfolio-panel.tsx"


def test_portfolio_panel_does_not_use_position_current_price_directly():
    """
    portfolio-panel 不能直接用 p.current_price(那是 API 落盘时的均价占位)
    应该用 currentPrices[symbol](K线有真实 last close 才算 PnL)
    """
    src = PANEL.read_text(encoding="utf-8")
    forbidden = ["p.current_price - p.avg_price", "sum + p.quantity * p.current_price"]
    for bad in forbidden:
        assert bad not in src, (
            f"portfolio-panel.tsx 直接用 p.current_price 算 PnL;"
            " 改用 currentPrices[symbol] 拉真现价"
        )


def test_kline_chart_writes_last_close_to_store():
    """KLineChart 拉真实 K 线成功后必须 setCurrentPrice"""
    kc = (REPO / "forgemind-ui" / "components" / "kline-chart.tsx").read_text(encoding="utf-8")
    assert "setCurrentPrice" in kc, (
        "kline-chart.tsx 拉 K 线后没把 last close 写到 store;"
        " portfolio-panel 的 PnL 永远是 0"
    )
    assert "useAppStore" in kc, (
        "kline-chart.tsx 没 import useAppStore,"
        " 拿不到 setCurrentPrice"
    )
