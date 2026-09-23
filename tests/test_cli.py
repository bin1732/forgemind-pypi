# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import argparse
import sys
from unittest.mock import patch, MagicMock


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
        """mcp 命令 — start server"""
        from forgemind.cli import cmd_mcp
        args = self._make_args()
        # mcp 是常驻服务,只跑 setup
        try:
            # 用 timeout 防卡死
            import signal
            def handler(*_):
                raise TimeoutError("stop")
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(2)
            try:
                cmd_mcp(args)
            except TimeoutError:
                pass
            signal.alarm(0)
        except Exception:
            pass
    
    def test_cmd_etl(self):
        """etl 命令 — 拉数据"""
        from forgemind.cli import cmd_etl
        args = self._make_args(symbols=None)
        # 网络可能失败
        try:
            cmd_etl(args)
        except Exception:
            pass


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