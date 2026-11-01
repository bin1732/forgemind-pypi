# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""行情数据的体检:自洽的通过,不自洽的必须报出来。

列序写错是最容易犯又最难发现的错 —— 文件读得出来、日期也对,只有
high/low 与 open/close 对不上。体检自己也要可靠:遇到读不懂的输入,
它得说"无法核对",不能崩,更不能当通过。
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from check_ohlc_sanity import main as check_main  # noqa: E402
from forgemind.core.data.ohlc import assert_ohlc, validate_ohlc  # noqa: E402


def _good() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [10.0, 11.0, 12.0],
            "high": [12.0, 13.0, 14.0],
            "low": [9.0, 10.0, 11.0],
            "close": [11.0, 12.0, 13.0],
            "volume": [100.0, 200.0, 300.0],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
    )


class TestValidateOhlc:
    def test_self_consistent_data_passes(self):
        assert validate_ohlc(_good()) == []

    def test_columns_swapped_is_reported(self):
        """列序写错 —— high 与 close 互换了,必须报出来

        这就是内置样例真踩过的那一种:文件读得出来、日期也对,只有
        high/low 与 open/close 对不上,要等策略在上面算出离谱的收益
        才暴露。
        """
        df = _good()
        df["high"], df["close"] = df["close"], df["high"]
        problems = validate_ohlc(df)
        assert problems, "列序写错没有被报出来"
        assert any("high" in p for p in problems)

    def test_close_written_into_low_column_is_reported(self):
        """收盘价被写进 low 列 —— high 仍然大于 low,但 low 大于 close"""
        df = _good()
        df["low"] = df["close"]
        problems = validate_ohlc(df)
        assert any("low" in p for p in problems), problems

    def test_high_below_low_is_reported(self):
        df = _good()
        df.loc[df.index[1], "high"] = 1.0
        problems = validate_ohlc(df)
        assert any("high" in p for p in problems)

    def test_non_positive_price_is_reported(self):
        df = _good()
        df.loc[df.index[0], "close"] = 0.0
        problems = validate_ohlc(df)
        assert any("价格" in p for p in problems)

    def test_negative_volume_is_reported(self):
        df = _good()
        df.loc[df.index[0], "volume"] = -1.0
        problems = validate_ohlc(df)
        assert any("成交量" in p for p in problems)

    def test_unsorted_dates_are_reported(self):
        df = _good()
        df = df.iloc[::-1]
        problems = validate_ohlc(df)
        assert any("递增" in p for p in problems)

    def test_missing_column_is_reported(self):
        df = _good().drop(columns=["volume"])
        problems = validate_ohlc(df)
        assert any("缺少列" in p for p in problems)

    def test_unreadable_input_says_cannot_verify_instead_of_crashing(self):
        """体检自己不能崩 —— 崩了等于没查"""
        problems = validate_ohlc(pd.DataFrame({"open": ["abc"], "high": ["x"], "low": ["y"], "close": ["z"], "volume": ["v"]}))
        assert problems
        assert any("无法核对" in p for p in problems)

    def test_empty_frame_is_reported(self):
        problems = validate_ohlc(pd.DataFrame(columns=["open", "high", "low", "close", "volume"]))
        assert problems

    def test_assert_ohlc_raises_with_the_reason(self):
        df = _good()
        df["high"], df["close"] = df["close"], df["high"]
        with pytest.raises(ValueError, match="不自洽"):
            assert_ohlc(df, "测试数据")


class TestBundledSample:
    def test_bundled_sample_is_self_consistent(self):
        """包内置的真实行情必须自洽 —— 它是 demo 的数据来源"""
        from forgemind.core.data import bundled_sample_path

        path = bundled_sample_path()
        assert path.is_file(), f"内置行情文件不存在:{path}"
        df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
        assert validate_ohlc(df) == []
        assert len(df) >= 200, "内置行情的交易日太少,回测跑不出有意义的结果"

    def test_checker_script_passes_on_the_bundled_sample(self, capsys):
        assert check_main() == 0
        assert "自洽" in capsys.readouterr().out
