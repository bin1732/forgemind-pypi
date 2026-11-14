# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP 输出判据:它自己也得可靠。

它盯的是"每个工具带合法参数真调一遍,输出里没有内部实现,库被占着时
说的是'读不到'而不是'没有数据'"。这类判据最容易出两种错:

- 规则太宽 ⇒ 一堆假红 ⇒ 没人看它。
- 规则太窄 ⇒ 真的漏了也放过。

所以这里逐条钉:该报的报、不该报的不报,而且用**编出来的输出**做样本 ——
真跑一遍能验"整条链路合规",却验不出**哪条规则**在起作用。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_mcp_output_clean as mcp_clean  # noqa: E402
import mcp_tool_probes as probes  # noqa: E402


class TestProbeTable:
    def test_every_declared_tool_has_legal_args(self):
        """tools/list 里的每个工具都要有合法参数。

        少一个,判据就漏了那个工具 —— 它出问题时没人会发现。新加工具
        忘了配参数,这一条当场报出来。
        """
        from forgemind.mcp.server import ForgeMindMCPServer

        server = ForgeMindMCPServer()
        declared = set(server.tools)
        probed = {name for name, _ in probes.TOOL_CALLS}
        assert declared == probed, (
            f"工具清单与参数表对不上:声明了没配参数的 {declared - probed},"
            f"配了但工具不存在的 {probed - declared}"
        )

    def test_store_touching_tools_are_declared(self):
        """会读库的工具有名单 —— 库被占着时要挨个核。"""
        assert "run_backtest" in probes.TOOLS_TOUCHING_STORE
        assert "get_kline" in probes.TOOLS_TOUCHING_STORE
        assert "search_features" not in probes.TOOLS_TOUCHING_STORE


class TestMarkers:
    def test_unreadable_and_missing_markers_are_different(self):
        """ "读不到"与"没有数据"必须是两套说法,不能混"""
        assert set(mcp_clean.UNREADABLE_MARKERS) & set(mcp_clean.MISSING_MARKERS) == set()

    def test_forbidden_kinds_are_internal_implementation(self):
        """不许出现的那几种,都是内部实现"""
        for kind in ("异常类名", "SQL 片段", "Python 栈回溯", "本机绝对路径"):
            assert kind in mcp_clean.FORBIDDEN


class TestLockedStateRules:
    """库被占着时的规则,用编出来的输出逐条钉"""

    def test_saying_missing_data_is_a_problem(self):
        problems = mcp_clean.check_locked_output(
            "run_backtest",
            '{"status": "no_data", "message": "本地库里没有 600519 的 K 线"}',
        )
        assert any("没有数据" in p for p in problems), problems

    def test_not_saying_unreadable_is_a_problem(self):
        problems = mcp_clean.check_locked_output("run_backtest", '{"status": "no_data"}')
        assert any("没说要读不到" in p for p in problems), problems

    def test_internal_implementation_is_a_problem(self):
        problems = mcp_clean.check_locked_output(
            "get_kline",
            '{"error": "读取行情失败:IOException: Could not write file /home/runner/work/main.db"}',
        )
        assert any("异常类型名" in p or "本机绝对路径" in p for p in problems), problems

    def test_compliant_output_has_no_problems(self):
        """合规的输出不该被报出问题 —— 规则太宽会让人不再看它"""
        problems = mcp_clean.check_locked_output(
            "run_backtest",
            '{"status": "store_unavailable", '
            '"error": "本地库正被另一个进程占用(桌面端开着时它就占着同一个库)。"}',
        )
        assert not problems, problems

    def test_empty_output_is_a_problem(self):
        problems = mcp_clean.check_locked_output("get_kline", "")
        assert problems, "没有返回内容也是一种问题"


class TestTheCheckerItselfRuns:
    def test_checker_passes_on_the_real_repo(self):
        """判据在真仓上要跑得通 —— 判据自己跑不起来,等于没有判据"""
        assert mcp_clean.main() == 0


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
