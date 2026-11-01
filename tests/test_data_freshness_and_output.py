# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""结论必须带着"依据有多新"一起呈现

量化工具最容易被忽视的误导:计算完全正确,但依据是几周前的收盘价。
用户看到"均线空头排列"和评分,却不知道那是上个月的形态。

我自己的旅程数据就是 2024-06-28 —— 830 天前,pick 照常给结论,
一个字都没提。加上新鲜度提示后,一眼就看出问题。

顺带:终端不渲染 markdown,`**...**` 直接印出来是一堆星号,看起来像
渲染坏了,反而削弱了它本该有的警示作用。
"""

import datetime as dt
import io
from contextlib import redirect_stdout


class TestDataFreshness:
    def test_today(self):
        from forgemind.core.data.storage import data_freshness

        t = dt.date.today()
        assert "今天" in data_freshness(t.isoformat(), today=t)

    def test_yesterday(self):
        from forgemind.core.data.storage import data_freshness

        t = dt.date.today()
        assert "昨天" in data_freshness((t - dt.timedelta(days=1)).isoformat(), today=t)

    def test_recent_is_not_alarmed(self):
        """3 天前不该报警 —— 否则用户对警告脱敏,真出事时也不看了"""
        from forgemind.core.data.storage import data_freshness

        t = dt.date.today()
        out = data_freshness((t - dt.timedelta(days=3)).isoformat(), today=t)
        assert "3 天前" in out
        assert "**" not in out, f"3 天前不该标成异常:{out}"

    def test_stale_is_flagged(self):
        from forgemind.core.data.storage import data_freshness

        t = dt.date.today()
        out = data_freshness((t - dt.timedelta(days=830)).isoformat(), today=t)
        assert "严重过期" in out and "forgemind etl" in out, out
        assert "**" in out, "严重过期必须被强调"

    def test_missing_data_is_not_silent(self):
        from forgemind.core.data.storage import data_freshness

        assert "未知" in data_freshness(None)

    def test_garbage_date_is_not_silent(self):
        from forgemind.core.data.storage import data_freshness

        assert "无法解析" in data_freshness("not-a-date")


class TestPickerRecordsTheDataDate:
    def test_attribute_exists_and_defaults_to_none(self):
        from forgemind.core.agents.stock_picker import StockPickerAgent

        assert getattr(StockPickerAgent(), "last_data_date", "missing") is None

    def test_cli_reports_it(self):
        """CLI 必须把数据日期打出来 —— 不打就等于没有这个信息"""
        import pathlib

        src = (pathlib.Path(__file__).resolve().parent.parent
               / "forgemind" / "cli.py").read_text(encoding="utf-8")
        assert "data_freshness" in src, "CLI 没有调用 data_freshness"
        assert "依据的行情最新日期" in src


class TestTerminalOutputIsNotMarkdown:
    """TTY 下把 ** 换成 ANSI 粗体,重定向时保留 markdown"""

    def test_plain_converts_bold_when_tty(self):
        from forgemind.cli import _plain

        class FakeTTY(io.StringIO):
            def isatty(self):
                return True

        with redirect_stdout(FakeTTY()):
            out = _plain("a **b** c")
        assert "**" not in out
        assert "\033[1m" in out and "b" in out

    def test_plain_keeps_markdown_when_not_tty(self):
        """重定向到文件时保留 markdown,便于后续渲染"""
        from forgemind.cli import _plain

        class NotTTY(io.StringIO):
            def isatty(self):
                return False

        with redirect_stdout(NotTTY()):
            out = _plain("a **b** c")
        assert "**b**" in out
        assert "\033[" not in out
    def test_main_wires_the_plinter_on_a_tty(self, monkeypatch):
        """main() 必须在 TTY 下把 print 换成会脱 markdown 的版本

        之前这条测的是 `forgemind backtest` 的横幅 —— 而那一行本来就有
        单独的 print(_plain(...)) 包裹,**把全局机制整个删掉测试照样绿**。
        断言必须落在全局机制本身上。
        """
        import builtins
        import sys as _sys

        import forgemind.cli as C

        class FakeTTY(io.StringIO):
            def isatty(self):
                return True

        fake = FakeTTY()
        monkeypatch.setattr(_sys, "stdout", fake)
        monkeypatch.setattr(_sys, "argv", ["forgemind", "backtest",
                                          "--strategy", "ma_cross",
                                          "--start", "2024-01-01",
                                          "--end", "2024-02-01"])
        orig = builtins.print
        try:
            try:
                C.main()
            except SystemExit:
                pass
            assert isinstance(builtins.print, C._PlainPrinter), (
                "TTY 下 main() 没有把 print 换成 _PlainPrinter")
        finally:
            builtins.print = orig

    def test_markdown_is_converted_in_a_real_terminal(self):
        """端到端:TTY 里跑确实会产出 markdown 的命令,确认终端看到的是 ANSI"""
        import os
        import pathlib
        import subprocess
        import sys

        env = {**os.environ, "FORGEMIND_LOG_LEVEL": "WARNING",
               "PYTHONPATH": str(pathlib.Path(__file__).resolve().parent.parent)}
        p = subprocess.run(
            ["script", "-qec",
             f"{sys.executable} -m forgemind.cli pick --top-n 1", "/dev/null"],
            capture_output=True, text=True, timeout=600, env=env,
        )
        assert "**" not in p.stdout, (
            f"TTY 输出里仍有 markdown 标记:\n{p.stdout[-500:]}")
