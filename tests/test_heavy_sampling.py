# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""重并发抽样策略:铺开在整个文件上,不能只取前几条。

**为什么盯这个**:抽样档是常规流水线里唯一跑重并发用例的地方。它只跑
一小部分用例,于是"抽到哪些"就直接决定了哪些回归能被当场抓住。

原来的取法是每个文件只留**前 k 条**。后果不是"少跑几条",而是**某些
逻辑路径永远跑不到**:实测过某个文件 38 条 heavy 用例只跑前 3 条,跑到的
偏偏是 info / signal / router-demo,而 backtest、agent、mcp、pick、etl 的
"跑两遍"路径一条都没进过抽样档 —— 那组用例在常规流水线里等于不存在。

所以这里用**合成的用例列表**逐条钉住取法:用真仓的全量用例去验,只会
得到"抽到了 150 条"这种没法判对错的结果。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import _sample_heavy_items  # noqa: E402


class _FakeItem:
    """够 _sample_heavy_items 用的最小用例对象。"""

    def __init__(self, nodeid: str):
        self.nodeid = nodeid

    def get_closest_marker(self, name: str):
        return object() if name == "heavy" else None


def _items(file_name: str, count: int) -> list[_FakeItem]:
    return [_FakeItem(f"tests/{file_name}::TestX::test_{i}") for i in range(count)]


class TestSamplingSpansTheWholeFile:
    def test_kept_items_are_not_just_the_head_of_the_file(self):
        """被抽到的不能全是文件开头的几条。"""
        items = _items("sample.py", 40)
        kept, dropped = _sample_heavy_items(items, 4)  # 每个文件取 10 条
        assert kept, "一个都没抽到"
        positions = {id(it): i for i, it in enumerate(items)}
        kept_positions = sorted(positions[id(it)] for it in kept)
        # 只取前 k 条的话,最靠后的被抽到的是第 10 条(下标 9)。
        # 铺开取的话,后面还会有被抽到的 —— 下标要超过 k。
        assert max(kept_positions) > 10, (
            f"抽样只落在文件头部(最靠后的是第 {max(kept_positions) + 1} 条):"
            f"文件靠后的用例在抽样档永远不会被执行"
        )

    def test_kept_items_are_spread_across_the_file(self):
        """抽到的用例要分散,不能挤在一处。"""
        items = _items("sample.py", 40)
        kept, _dropped = _sample_heavy_items(items, 4)
        positions = {id(it): i for i, it in enumerate(items)}
        kept_positions = sorted(positions[id(it)] for it in kept)
        gaps = [b - a for a, b in zip(kept_positions, kept_positions[1:])]
        # 铺开取的最大间隔不超过文件长度 / 条数 + 1
        assert max(gaps) <= 40 // 10 + 1, f"抽样挤在一处,间隔 {gaps}"

    def test_every_file_still_gets_a_representative(self):
        """按文件分组这个约定不能丢:每个文件至少留一条。"""
        items = (
            _items("a.py", 3)
            + _items("b.py", 30)
            + _items("c.py", 1)
        )
        kept, _dropped = _sample_heavy_items(items, 10)
        kept_files = {it.nodeid.split("/")[-1].split("::")[0] for it in kept}
        assert kept_files == {"a.py", "b.py", "c.py"}, kept_files

    def test_ratio_one_keeps_everything(self):
        """完整规模档关掉抽样时,一条都不能少。"""
        items = _items("a.py", 17)
        kept, dropped = _sample_heavy_items(items, 1)
        assert len(kept) == 17
        assert not dropped

    def test_no_heavy_items_are_left_alone(self):
        """没有 heavy 用例时,原样返回。"""
        items = [_FakeItem("tests/x.py::TestY::test_0")]
        kept, dropped = _sample_heavy_items(items, 10)
        assert len(kept) == 1 and not dropped
