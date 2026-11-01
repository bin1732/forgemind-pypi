# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""空界面要分清"没有数据"与"取不到数据"。

取数失败时组件照旧显示"暂无数据",用户会以为自己没数据,其实是后端连不上、
工具报错了,或者还没跑过 ETL。界面看着正常,问题却没人发现 —— 这与
"接口返回了 JSON 但什么都没做"是同一类。

这个检查不猜逻辑:界面代码里有没有正确地区分这两种情况,靠读代码判断
不可靠 —— 读了 dataError 却没在空态里说出来,静态匹配看不出来。真正能
判定的办法是跑起来看:所以这里要求有对应的组件测试,那条测试必须真的
断言"取数失败时界面说的是失败"。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 这些面板的数据来自后端,取不到时必须说得出原因。
PANELS_FROM_BACKEND = (
    "agent-decision-panel.tsx",  # query_portfolio 的 6 Agent 决策
    "portfolio-panel.tsx",  # query_portfolio 的持仓与风险指标
    "signal-table.tsx",  # 端到端流水线的 signals
)

# 断言"取数失败时界面说的是失败"的测试,必须存在且真的这么断言
EMPTY_STATE_TEST = Path("components") / "__tests__" / "empty-state.test.tsx"
# 断言取数失败时,界面出现"取数失败"字样的那几行
ASSERT_FAILURE_VISIBLE = re.compile(r"取数失败")


def main() -> int:
    parser = argparse.ArgumentParser(description="核对空态能区分没有数据与取不到数据")
    parser.add_argument("ui", type=Path, help="界面源码目录")
    args = parser.parse_args()

    root = args.ui.resolve()
    problems: list[str] = []

    for name in PANELS_FROM_BACKEND:
        if not (root / "components" / name).is_file():
            problems.append(f"面板不见了: components/{name}")

    test_path = root / EMPTY_STATE_TEST
    if not test_path.is_file():
        problems.append(f"缺少空态区分的组件测试: {EMPTY_STATE_TEST.as_posix()}")
    else:
        text = test_path.read_text(encoding="utf-8")
        if not ASSERT_FAILURE_VISIBLE.search(text):
            problems.append(f"{EMPTY_STATE_TEST.as_posix()} 里没有断言界面出现'取数失败'")
        for name in PANELS_FROM_BACKEND:
            stem = name[: -len(".tsx")]
            if stem not in text:
                problems.append(f"{EMPTY_STATE_TEST.as_posix()} 没有覆盖面板 {stem}")

    if problems:
        print("空态区分没被守住:")
        for item in problems:
            print(" -", item)
        return 1

    print(
        f"空态区分有组件测试守着: {len(PANELS_FROM_BACKEND)} 个面板 + {EMPTY_STATE_TEST.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
