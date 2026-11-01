# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""数据接入层。"""

from pathlib import Path


def bundled_sample_path() -> Path:
    """包内置的真实历史行情文件路径。

    文件里是历史事实,不是模拟数据 —— 详见 forgemind/data/README.md。
    """
    return Path(__file__).resolve().parent.parent.parent / "data" / "sample_600519_2024.csv"
