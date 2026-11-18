# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对界面上的数值来自后端,不是写死在组件里。

"真数据驱动"这条结论不该只是一句话:组件里如果留着写死的指标值,
界面看起来正常,后端却可能早已不返回这些数了。这个检查逐个组件扫,
发现疑似写死的数值就报出来。

判定刻意保守,宁可漏报也不误报:只挑明显是指标值的浮点字面量,
样式相关的数值(字号、间距、透明度、百分比)一律放过。

另外盯一类新的:对象字面量里,账户类字段跟着数值字面量。界面替用户
编一个账户(现金十万、持仓一百股),后端照着算,结论看着正常,依据是
假的 —— 而整数写死的金额躲过了浮点那条规则。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 两位以上小数的浮点字面量,像指标值
METRIC_VALUE = re.compile(r"(?<![\w.])[-+]?\d+\.\d{2,}(?![\w.])")
# 样式相关的数值,不是指标
#
# 单位一律要求**前面是数字**(0.5s、12px、2rem)。不要求的话,"args"、
# "positions"、"system"、"params" 这些普通词里的 s / em / ms 会把
# 整行判成样式行 —— 于是那一行不管写了什么写死的数据都看不见。
# 漏判比误判更难发现:检查器还是绿的。
STYLE_CONTEXT = re.compile(
    r"(z-index|opacity|font-?size|line-?height|margin|padding|gap|"
    r"width|height|top|left|right|bottom|transform|transition|"
    r"(?<=\d)(?:rem|em|px|vh|vw|deg|ms|s\b)|%)",
    re.I,
)
# 组件里常见的常量名,命中即视为写死的数据
FIXTURE_NAMES = re.compile(
    r"\b(?:MOCK|FAKE|DUMMY|SAMPLE|STATIC|PLACEHOLDER|DEMO)_\w+",
    re.I,
)
# 对象字面量里,账户类字段跟着数值字面量 —— 界面替用户编了状态。
#
# 上面那条只挑两位以上小数的浮点,整数写死的账户(现金十万、持仓一百
# 股)从它眼前走过去了,而那正是界面编账户最常见的写法。账户类字段
# 跟着字面量,一律报出来。
ACCOUNT_LITERAL = re.compile(
    r"\b(?:cash|total_equity|equity|balance|capital|amount|quantity|"
    r"avg_price|market_value|position_value|shares)\s*:\s*[-+]?\d+(?:\.\d+)?",
    re.I,
)


#: 比较表达式里的常量是阈值,不是显示值。
#:
#: "IC 大于 0.02 就标绿"是界面规则,规则就该写死在代码里;要盯的是
#: **显示给用户看**的那个数 —— 那种数一改,后端早就不返回它了,界面
#: 却还摆着一个像模像样的值。
THRESHOLD_BEFORE = re.compile(r"(?:[<>]=?|==|!=)\s*$")


def _metric_values(line: str) -> list[re.Match[str]]:
    """这一行里像指标值的浮点字面量(阈值不算)。"""
    out = []
    for match in METRIC_VALUE.finditer(line):
        before = line[: match.start()]
        if THRESHOLD_BEFORE.search(before):
            continue
        out.append(match)
    return out


def check_file(path: Path) -> list[tuple[int, str]]:
    """返回一个文件里疑似写死数据的位置。"""
    problems = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if STYLE_CONTEXT.search(line):
            continue
        if ACCOUNT_LITERAL.search(line):
            problems.append((number, line.strip()[:110]))
            continue
        if _metric_values(line):
            problems.append((number, line.strip()[:110]))
            continue
        if FIXTURE_NAMES.search(line):
            problems.append((number, line.strip()[:110]))
    return problems


# 不是我们自己的代码:第三方依赖与构建产物
SKIP_DIRS = {"node_modules", ".next", "out", "dist", "build", ".git"}


def check_tree(root: Path) -> tuple[list[str], int]:
    """扫一棵界面源码树,返回 (问题清单, 看过的文件数)。

    目录做参数而不是写死 —— 这样检查器自己的行为能在临时目录里验。
    """
    problems: list[str] = []
    files = 0
    for path in sorted(root.rglob("*.tsx")) + sorted(root.rglob("*.ts")):
        if "__tests__" in path.parts or "__mocks__" in path.parts:
            continue
        # 第三方与构建产物不是我们的界面 —— 扫进去只会被它们自己的常量
        # 淹没。兄弟检查器 check_ui_mock_isolation 也是这么排除的。
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files += 1
        for number, line in check_file(path):
            rel = path.relative_to(root)
            problems.append(f"{rel}:{number}  {line}")
    return problems, files


def main() -> int:
    """扫描界面组件,返回进程退出码。"""
    parser = argparse.ArgumentParser(description="核对界面上的数值是否写死")
    parser.add_argument("ui", type=Path, help="界面源码目录")
    args = parser.parse_args()

    root = args.ui.resolve()
    if not root.is_dir():
        print(f"找不到目录: {root}", file=sys.stderr)
        return 2

    problems, files = check_tree(root)

    if problems:
        print(f"界面里有 {len(problems)} 处疑似写死的数据:")
        for item in problems:
            print(" -", item)
        return 1

    print(f"界面数据全部来自后端: {files} 个组件文件,没有写死的指标值")
    return 0


if __name__ == "__main__":
    sys.exit(main())
