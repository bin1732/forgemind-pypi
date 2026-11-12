# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP 工具的"能不能真算出东西"验证

两个真实缺陷,都是工具**从未成功过**却一直返回体面错误的那种:

1. `check_ic_decay` 调用 `compute_ic_decay(feature_name, window_days=...)`,
   而后者签名是 `(LazyFrame, 因子列, 前瞻收益列列表)`。TypeError 被 catch
   住之后还甩锅说"需要本地行情数据",于是这个工具永远失败,且原因提示是错的。
   更糟的是它之后还去读 `n_obs` / `ic_mean` / `icir`,而真实返回值是
   `{days: ic}` —— 即使签名对上了,解析照样全错。

2. `stock_pick` 静默返回 0 picks。DuckDB 里的代码是 6 位,而 MCP 其它工具
   (`run_backtest` / `output_signal`)都用 `600519.SH`。同一个协议里两套写法,
   传后缀就查不到数据,用户完全看不出来。

"返回了 JSON"不等于"干了活" —— 这两个工具都返回了完美的 JSON-RPC 响应。
"""

import asyncio
import inspect
from pathlib import Path

import pytest

from forgemind.mcp.server import ForgeMindMCPServer

ROOT = Path(__file__).resolve().parent.parent


class TestSymbolNormalization:
    @pytest.mark.parametrize(("raw", "expected"), [
        ("600519.SH", "600519"),
        ("000001.SZ", "000001"),
        ("sh600519", "600519"),
        ("SZ000001", "000001"),
        ("600519", "600519"),
        (" 600519 ", "600519"),
        ("600519-sh", "600519"),
    ])
    def test_bare_symbol(self, raw, expected):
        assert ForgeMindMCPServer._bare_symbol(raw) == expected

    def test_mcp_protocol_does_not_have_two_symbol_dialects(self):
        """run_backtest / output_signal 用带后缀,stock_pick 必须能接住

        真实用户旅程里就是这么撞上的:用 600519.SH 调 stock_pick 静默返回
        0 picks,而同一套协议里 run_backtest 用的就是 600519.SH。
        """

        src = (ROOT / "forgemind/mcp/server.py").read_text(encoding="utf-8")
        assert "_bare_symbol" in src, "stock_pick 必须归一化,否则与其它工具不一致"
        seg = src[src.index("async def _tool_stock_pick"):
                  src.index("def _bare_symbol")]
        assert "_bare_symbol" in seg, "stock_pick 实际调用链里必须真的用它"


class TestCheckIcDecayCallsTheRealFunction:
    def test_mcp_call_signature_matches_the_function(self):
        """签名对不上是这个 bug 的根源,直接比对"""
        from forgemind.core.factors.ic_monitor import compute_ic_decay

        params = list(inspect.signature(compute_ic_decay).parameters)
        assert params[0] == "factor_df", (
            "compute_ic_decay 第一个参数变了,MCP 侧必须同步检查")
        assert params[1] == "factor_col"
        assert params[2] == "forward_returns_cols"

        src = (ROOT / "forgemind/mcp/server.py").read_text(encoding="utf-8")
        # 不能再出现把因子名当第一参数传的写法
        assert "compute_ic_decay(feature_name" not in src, (
            "compute_ic_decay 要 LazyFrame,不是因子名")
        assert "compute_ic_decay(window_days" not in src, (
            "window_days 不是 compute_ic_decay 的参数")

    def test_error_message_carries_the_cause(self, monkeypatch):
        """失败信息要带上异常内容,也不能只有类名

        不能再只报 type(exc).__name__ —— 那是把问题踢回给用户;但类名本身
        是内部实现,也不该出现在给模型看的文字里(模型看到 "RuntimeError"
        只会以为服务坏了)。

        这里盯**行为**:真让读取失败一次,看它报的是什么。原来那条用例盯
        的是源码里的一行字面量,换个写法就红 —— 行为没变,重构一下就红,
        那是脆的判据。
        """
        import forgemind.core.data.storage as storage

        class _Boom:
            def __enter__(self):
                raise RuntimeError("行情库炸了")

            def __exit__(self, *exc_info):
                return False

        monkeypatch.setattr(storage, "DuckDBStorage", _Boom)
        result = asyncio.run(ForgeMindMCPServer()._tool_check_ic_decay("kmid", window_days=5))
        assert result.get("error"), result
        message = result["error"]
        assert "行情库炸了" in message, f"失败信息丢了原因: {message}"
        assert "RuntimeError" not in message, f"失败信息里不该有异常类名: {message}"


class TestStockPickExplainsEmptyResults:
    def _run(self, universe):
        return asyncio.run(ForgeMindMCPServer()._tool_stock_pick(universe, top_n=2))

    def test_response_always_declares_status(self):
        """空结果必须说明是'没数据'还是'算过了没选出来'"""
        r = self._run(["__definitely_not_a_symbol__"])
        assert r["status"] in ("ok", "insufficient_data", "empty")
        if not r["picks"]:
            assert r["status"] != "ok", "空 picks 不能标 ok"
            assert r.get("hint"), "空结果必须给出下一步"

    def test_universe_is_normalized_in_the_response(self):
        r = self._run(["600519.SH", "000001.SZ"])
        assert r["universe"] == ["600519", "000001"]


class TestTestsDoNotDependOnCwd:
    """回归测试本身不能在 CWD 变化时崩

    这条是被全量跑打出来的:单独跑通过,全量跑 FileNotFoundError,
    因为读源码用的是相对路径。测试基础设施出问题时,看到的是
    "测试失败",而真实原因(路径)被埋掉了。
    """

    def test_source_reads_use_repo_root(self):
        assert (ROOT / "forgemind/mcp/server.py").exists()
        src = (ROOT / "forgemind/mcp/server.py").read_text(encoding="utf-8")
        assert "_tool_check_ic_decay" in src

    def test_works_from_any_cwd(self, tmp_path, monkeypatch):
        """换到别的目录,ROOT 解析仍须成立

        原实现是 spawn 一个完整 pytest 子进程来验证这一点 —— 但子进程
        跑的也是这个文件,于是它又会 spawn 一个,指数级递归,把自己拖死。
        真正要断言的是"ROOT 解析与 CWD 无关",直接验证即可。
        """
        monkeypatch.chdir(tmp_path)
        assert Path("forgemind/mcp/server.py").resolve() != (ROOT / "forgemind/mcp/server.py")
        assert (ROOT / "forgemind/mcp/server.py").exists()
        src = (ROOT / "forgemind/mcp/server.py").read_text(encoding="utf-8")
        assert "_tool_check_ic_decay" in src
