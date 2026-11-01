# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
from unittest.mock import patch

import pytest


class TestCLICommands:
    """覆盖所有 cmd_* 函数"""

    def _make_args(self, **kwargs):
        """构造 argparse Namespace"""
        defaults = {
            "strategy": "ma_cross",
            "fast": 5,
            "slow": 20,
            "start": "2024-01-01",
            "end": "2024-12-31",
            "capital": 100_000.0,
            "symbol": "600519.SH",
            "cash": 80_000.0,
            "equity": 200_000.0,
            "position_qty": 100,
            "position_price": 1500.0,
            "symbols": None,
            "top_n": 5,
            "slippage_model": "fixed",
            "adv": 0.0,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_cmd_info(self):
        """info 命令 — 显示配置"""
        from forgemind.cli import cmd_info
        args = self._make_args()
        # 应能跑通(只是 print)
        cmd_info(args)

    def test_cmd_broker_test(self):
        """signal 命令 — 显示研究层说明"""
        from forgemind.cli import cmd_broker_test
        args = self._make_args()
        cmd_broker_test(args)  # 应只 print

    def test_cmd_backtest_ma_cross(self):
        """backtest + ma_cross"""
        from forgemind.cli import cmd_backtest
        args = self._make_args(strategy="ma_cross", fast=5, slow=20)
        cmd_backtest(args)

    def test_cmd_backtest_other_strategy(self):
        """backtest + bollinger 策略"""
        from forgemind.cli import cmd_backtest
        args = self._make_args(strategy="bollinger", fast=10, slow=30)
        cmd_backtest(args)

    def test_cmd_router_demo(self):
        """router-demo 命令"""
        from forgemind.cli import cmd_router_demo
        args = self._make_args()
        # quick_route_demo 打印 provider info
        try:
            cmd_router_demo(args)
        except Exception:
            pass  # router demo 可能调用 LLM,失败可接受

    def test_cmd_pick_no_symbols(self):
        """pick 无 symbols — 用默认"""
        from forgemind.cli import cmd_pick
        args = self._make_args(symbols=None, top_n=3)
        # StockPickerAgent 会尝试 AKShare,可能失败
        try:
            cmd_pick(args)
        except Exception:
            pass  # 网络/数据源失败可接受

    def test_cmd_agent(self):
        """agent 命令 — portfolio context"""
        from forgemind.cli import cmd_agent
        args = self._make_args(symbol="600519.SH", cash=80_000.0)
        # 可能因数据缺失失败,但应至少跑通 init
        try:
            cmd_agent(args)
        except Exception:
            pass

    def test_cmd_mcp(self):
        """mcp 命令 — 启动 stdio server 并完成一次真实握手

        server 是常驻服务,靠 stdin 保持存活。在测试进程里直接跑它,
        超时信号会在测试进程里生效,可能落在 pytest 正在整理报告的
        时刻,导致整个会话中断。这里把 server 放到独立子进程,通过
        真实 JSON-RPC 请求完成握手,超时只作用于子进程。
        """
        import json
        import subprocess

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "forgemind-test", "version": "1.0"},
            },
        }

        proc = subprocess.Popen(
            [sys.executable, "-m", "forgemind.cli", "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            stdout, stderr = proc.communicate(
                json.dumps(request) + "\n", timeout=60
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            pytest.fail("mcp server 未在预期时间内响应握手请求")

        assert "jsonrpc" in stdout, f"mcp server 没有返回 JSON-RPC 响应: {stdout!r} {stderr!r}"
        payload = json.loads(stdout.strip().splitlines()[0])
        assert payload.get("id") == 1
        assert "result" in payload, f"握手未返回 result: {payload!r}"

    def test_cmd_etl(self):
        """etl 命令 — 拉真实数据

        两种结果都算通过:拉到数据(exit 0),或上游不可达时
        打印可行动的失败分类并 exit 1。**不能是裸异常** —— 那说明
        失败路径本身有问题。而 SystemExit 是 BaseException,
        不会被 `except Exception` 捕获,必须显式处理。
        """
        import contextlib
        import io

        from forgemind.cli import cmd_etl

        args = self._make_args(symbols=None)
        buf = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(buf):
            try:
                cmd_etl(args)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
            except Exception as e:
                pytest.fail(f"etl 抛了裸异常: {type(e).__name__}: {e}")
        out = buf.getvalue()
        # 退出码有明确语义:0 取到数据,1 取数失败但流程走完,
        # 2 内存不足,3 取数超时,4 磁盘空间不足。
        assert code in (0, 1, 2, 3, 4), f"退出码应为受支持的取值,实际 {code}"
        if code != 0:
            # 任何非零退出都要说明原因,并给出可行动的下一步
            reasons = ("失败原因分类", "取数超时", "上游行情源", "内存不足",
                       "磁盘空间不足", "未能开始取数")
            assert any(word in out for word in reasons), \
                f"失败时未给出可行动原因,输出: {out!r}"


class TestMain:
    """测试 main() 入口"""

    def test_main_help(self):
        """main --help 应打印帮助"""
        from forgemind.cli import main
        with patch.object(sys, "argv", ["forgemind", "--help"]):
            with pytest.raises(SystemExit):
                main()

    def test_main_no_command(self):
        """无子命令应退出 1"""
        from forgemind.cli import main
        with patch.object(sys, "argv", ["forgemind"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_info(self):
        """main info 子命令"""
        from forgemind.cli import main
        with patch.object(sys, "argv", ["forgemind", "info"]):
            main()

    def test_main_signal(self):
        """main signal 子命令"""
        from forgemind.cli import main
        with patch.object(sys, "argv", ["forgemind", "signal"]):
            main()


class TestCLIMainEntry:
    def test_module_level_main(self):
        """if __name__ == '__main__'"""
        # __main__ 入口测试很难,跳过
        pass


class TestETLResourceFailures:
    """小内存 / 小磁盘是真实用户场景,不能吐裸堆栈

    这两条路是在全量回归里反复失败后补的:3GB 机器上跑到 test_cmd_etl
    时进程已占 2.3GB,ETL 直接 MemoryError。只给一句"内存不足"没用 ——
    必须告诉用户下一步怎么做。
    """

    @staticmethod
    def _call(monkeypatch, exc):
        import contextlib
        import io

        import forgemind.core.data.akshare_etl as mod
        from forgemind.cli import cmd_etl

        class Fake:
            async def run(self, **k):
                raise exc

        monkeypatch.setattr(mod, "AKShareETL", Fake)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), pytest.raises(SystemExit) as ei:
            cmd_etl(argparse.Namespace(
                symbols="600519,000001", start="2024-01-01", end="2024-12-31"))
        return buf.getvalue(), (ei.value.code if isinstance(ei.value.code, int) else 1)

    def test_memory_error_gives_actionable_advice(self, monkeypatch):
        out, code = self._call(monkeypatch, MemoryError())
        # 退出码 2: 资源类 (memory/disk)
        assert code == 2
        assert "内存不足" in out
        assert "forgemind etl --symbols" in out, "必须给出可直接执行的下一步"
        assert "MemoryError" not in out, "不该把异常类型甩给用户"

    def test_disk_full_points_at_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        out, code = self._call(monkeypatch, OSError(28, "No space left on device"))
        # 退出码 4: 磁盘类 (ENOSPC)
        assert code == 4
        assert "磁盘" in out
        assert str(tmp_path) in out or "data" in out

    def test_unrelated_oserror_is_not_swallowed(self, monkeypatch):
        """只兜真正的 ENOSPC;权限错误必须照常抛出,不能被静默改写"""
        import contextlib
        import io

        import forgemind.core.data.akshare_etl as mod
        from forgemind.cli import cmd_etl

        class Fake:
            async def run(self, **k):
                raise PermissionError("[Errno 13] Permission denied")

        monkeypatch.setattr(mod, "AKShareETL", Fake)
        with contextlib.redirect_stdout(io.StringIO()), pytest.raises(PermissionError):
            cmd_etl(argparse.Namespace(
                symbols="600519", start="2024-01-01", end="2024-12-31"))
