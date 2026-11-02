# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""体检:行情数据必须自洽。

列序写错这类错,读得出来、日期也对,只有 high/low 与 open/close 对不上,
要等某个策略在它上面算出离谱结果才暴露。这里把"自洽"写成代码,由数据
入口与流水线各自把关。

用法:
    python scripts/check_ohlc_sanity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# 直接跑的时候要把仓根放进导入路径(环境里可能装过同名旧副本)。
# 但只在直接跑时放:被用例当模块导入时也放的话,源码树会压过装好的
# 发行包 —— "跑在发布出去的 wheel 上"那一档就悄悄测回源码树了。
if __name__ == "__main__":
    sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402

from forgemind.core.data.ohlc import validate_ohlc  # noqa: E402


def main() -> int:
    from forgemind.core.data import bundled_sample_path

    problems: list[str] = []
    path = bundled_sample_path()
    if not path.is_file():
        print(f"找不到内置行情文件:{path}")
        return 1
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    issues = validate_ohlc(frame)
    if issues:
        print(f"内置行情文件不自洽({path.name}):")
        for item in issues:
            print(f" - {item}")
        problems.extend(issues)
    else:
        print(f"内置行情文件自洽({path.name},{len(frame)} 根日线)")

    if problems:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
