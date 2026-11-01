# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""行情数据的体检:开高低收量必须自洽。

列序写错是这类数据最常见也最难发现的错 —— 文件读得出来、日期也对,
只有 high/low 与 open/close 对不上,而且要等到某个策略在它上面算出
一个离谱的结果时才暴露出来。有一回内置样例就踩了这个坑:收盘价被写
进了 high 列,引擎算出来的收益跟真实价格完全对不上。

所以这里把"什么算自洽"写成代码,由数据入口自己把关:

- high ≥ max(open, close)
- low ≤ min(open, close)
- high ≥ low
- 价格为正,成交量不为负
- 日期单调递增、不重复

返回**问题清单**而不是抛异常:调用方决定是要拒绝这份数据,还是只
提示一句。
"""

from __future__ import annotations

from typing import Any

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def validate_ohlc(frame: Any) -> list[str]:
    """检查一份行情数据是否自洽,返回问题清单(空 = 自洽)。

    遇到读不懂的输入时返回一条"无法核对",而不是抛异常 —— 一道体检
    自己崩掉,比它报出问题更糟:崩了会让人以为数据没问题,而实际上
    什么都没查。
    """
    problems: list[str] = []
    if frame is None:
        return ["没有数据"]
    try:
        n = len(frame)
    except TypeError:
        return ["无法核对:不是一张表"]
    if n == 0:
        return ["没有数据"]

    raw_columns = getattr(frame, "columns", None)
    columns = set(raw_columns) if raw_columns is not None else set()
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        return [f"缺少列:{', '.join(missing)}"]

    idx = frame.index
    # 日期单调递增且不重复
    if hasattr(idx, "is_monotonic_increasing") and not idx.is_monotonic_increasing:
        problems.append("日期不是递增的")
    if hasattr(idx, "has_duplicates") and idx.has_duplicates:
        problems.append("日期有重复")

    try:
        o = frame["open"].astype(float)
        h = frame["high"].astype(float)
        low = frame["low"].astype(float)
        c = frame["close"].astype(float)
        v = frame["volume"].astype(float)
    except (TypeError, ValueError) as exc:
        return [f"无法核对:价格列不是数值({type(exc).__name__})"]

    bad_high = (h < o) | (h < c)
    bad_low = (low > o) | (low > c)
    bad_range = h < low
    bad_price = (o <= 0) | (h <= 0) | (low <= 0) | (c <= 0)
    bad_volume = v < 0

    for label, mask in (
        ("high 小于 open 或 close", bad_high),
        ("low 大于 open 或 close", bad_low),
        ("high 小于 low", bad_range),
        ("价格不是正数", bad_price),
        ("成交量为负", bad_volume),
    ):
        n_bad = int(mask.sum())
        if n_bad:
            problems.append(f"{n_bad} 行的{label}")

    return problems


def assert_ohlc(frame: Any, where: str = "行情数据") -> None:
    """不自洽就抛错,并把问题说清楚。"""
    problems = validate_ohlc(frame)
    if problems:
        raise ValueError(f"{where}不自洽:{'; '.join(problems)}")
