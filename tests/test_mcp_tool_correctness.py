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


class TestIcStatisticsUseTheSameDefinition:
    """IC 均值与 ICIR 必须是同一个口径。

    仓里有两处能算出 IC 统计量:`ic_monitor.compute_ic`(逐期横截面 IC
    的时间序列)与 MCP 的 `check_ic_decay`。以前 MCP 自己拿"各 horizon
    的 IC"求均值与标准差,得出的 `icir` **不是 ICIR** —— 那些 IC 不是同一
    分布的重复样本,horizon 越长越低越平滑,离散度反映的是 horizon 的
    差异,不是因子表现的稳定性。

    桌面端的因子卡片显示的就是 MCP 这个值,口径不对,界面上就在显示
    一个名不副实的指标。所以这里做三方对拍:MCP 报的数必须与
    `ic_monitor` 算出来的一致。
    """

    @staticmethod
    def _seed(db_path, symbols=("600519", "000001"), days=90):
        import datetime as dt

        from forgemind.core.data.storage import DuckDBStorage

        with DuckDBStorage() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS kline_daily ("
                "date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, "
                "close DOUBLE, volume BIGINT, provider VARCHAR, "
                "PRIMARY KEY (date, symbol))"
            )
            rows = []
            for si, sym in enumerate(symbols):
                for i in range(days):
                    d = dt.date(2024, 1, 1) + dt.timedelta(days=i)
                    if d.weekday() >= 5:
                        continue
                    # 走一个能算出非平凡 IC 的价格路径:趋势 + 周期
                    close = 100.0 * (1 + 0.001 * (si + 1)) ** i
                    close *= 1.0 + 0.01 * ((-1) ** (i % 5))
                    rows.append(
                        (
                            d,
                            sym,
                            close * 0.998,
                            close * 1.005,
                            close * 0.995,
                            round(close, 4),
                            1_000_000,
                            "test",
                        )
                    )
            for row in rows:
                db.execute(
                    "INSERT INTO kline_daily (date, symbol, open, high, low, close, "
                    "volume, provider) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    list(row),
                )

    def test_mcp_icir_matches_ic_monitor(self, tmp_path, monkeypatch):
        import json

        import forgemind.core.config.settings as settings_mod

        db_path = tmp_path / "main.db"
        monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(db_path))
        settings_mod.get_settings.cache_clear()
        settings_mod.get_settings().duckdb_path = str(db_path)

        self._seed(db_path)

        server = ForgeMindMCPServer()

        # 因子名要经解析拿到真名 —— 工具内部也是这么做的,这里必须用
        # 同一个名字,否则两边算的根本不是同一个因子。
        from forgemind.core.factors import get_all_factors

        resolved = server._resolve_factor_name("kmid", get_all_factors())
        assert resolved, "kmid 应能解析到一个真因子"

        result = asyncio.run(
            server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "check_ic_decay",
                        "arguments": {"feature_name": "kmid", "window_days": 30},
                    },
                }
            )
        )
        text = result["result"]["content"][0]["text"]
        payload = json.loads(text)
        assert payload.get("status") == "computed", payload

        # 独立算一遍:同样的数据、同样的因子与前瞻收益,走 ic_monitor。
        import polars as pl

        from forgemind.core.factors import compute_forward_returns
        from forgemind.core.factors.alpha158 import compute_alpha158
        from forgemind.core.factors.ic_monitor import compute_ic
        from forgemind.core.data.storage import DuckDBStorage

        with DuckDBStorage() as db:
            pdf = db.query_df(
                "SELECT symbol, date, open, high, low, close, volume "
                "FROM kline_daily ORDER BY symbol, date"
            )
        lf = pl.from_pandas(pdf).lazy()
        with_factors = compute_alpha158(lf)
        horizons = sorted({1, 5, 10, 20} | {30})
        with_returns = compute_forward_returns(with_factors, horizons)
        expected = compute_ic(with_returns, resolved, "fwd_return_1")

        assert payload["icir"] == pytest.approx(float(expected.icir), abs=1e-9), (
            f"MCP 报的 ICIR({payload['icir']})与 ic_monitor 算的"
            f"({expected.icir})不是同一个口径"
        )
        assert payload["ic_mean"] == pytest.approx(float(expected.ic_mean), abs=1e-9), (
            f"MCP 报的 IC 均值({payload['ic_mean']})与 ic_monitor 算的"
            f"({expected.ic_mean})不是同一个口径"
        )
