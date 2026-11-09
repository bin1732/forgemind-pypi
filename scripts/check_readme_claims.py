# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对 README 里写着的活数字与真实情况一致。

README 里的因子数、策略数、测试规模都是**会随代码变的事实**:加一个
因子、删一个用例,数字就悄悄过期了,而文档还在自信地写着旧值。没有任何
检查守着这件事,过期只能靠人偶然发现。

这个脚本把 README 里出现过的活数字都对上:

- 因子总数,以及 Alpha158 / Alpha101 的拆分
- 可用策略数
- 测试规模(文件数 / 用例总数 / 常规档 / 重并发档)

**写了才核** —— README 没写的项直接跳过,不会硬套。代码不在同一个目录
时用 --code 指过去。

用法:
    python scripts/check_readme_claims.py README.md
    python scripts/check_readme_claims.py README.md --code <源码目录>
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# 「169 Alpha Factors」
FACTOR_TOTAL = re.compile(r"(\d+)[ \t]+Alpha[ \t]+Factors", re.I)
# 「Alpha158 (152) · Alpha101 (11)」
ALPHA_SPLIT = re.compile(r"Alpha158\s*\((\d+)\).{0,20}?Alpha101\s*\((\d+)\)", re.S)
# 「17 策略」
STRATEGY_COUNT = re.compile(r"(\d+)[ \t]*策略")
# 「9 LLM providers」与「**9 providers**」
PROVIDER_COUNT = re.compile(r"(\d+)[ \t]*(?:LLM[ \t]*)?providers", re.I)
# 「# 645 test files · 10083 tests」
TEST_SCALE = re.compile(r"#[ \t]*(\d+)[ \t]+test files[ \t]*·[ \t]*(\d+)[ \t]+tests")
# 「# 8246 cases」/「# 1837 cases」
# 空白不跨行:否则会跨过整段代码块去匹配别处的数字
CASE_LINES = re.compile(r"^#[ \t]*(\d+)[ \t]+cases[ \t]*$", re.M)
# 文档里带反引号的标识符
CODE_TOKEN = re.compile(r"`([a-z][a-z0-9_]*)`")
# 文档里写的 MCP 能力数量:「N 个 MCP 工具」
MCP_TOOL_COUNT = re.compile(r"(\d+)[ \t]*个[ \t]*MCP[ \t]*工具")

# 允许出现在文档里的其它标识符(不是 MCP 原语名),以及理由
ALLOWED_OTHER_TOKENS = {
    "forgemind": "包名本身",
    # 发布清单里的字段名。清单不是 MCP 原语,但公开仓的 README 要写清
    # "这次发布的版本号记在清单的哪个字段里",不写就成了空话。
    "published_version": "发布清单里的字段名,不是 MCP 原语",
}

# 文档里声称用到的技术 -> 源码里必须能找到的关键词。
# 只有说法没有实现,或者实现换了说法而文档没跟上,都会在这里被抓住。
TECH_CLAIMS = {
    "LangGraph": "langgraph",
    "DuckDB": "duckdb",
    "ClickHouse": "clickhouse",
    "AKShare": "akshare",
}

# 架构图里允许出现的括号说明。只有这几个是真的:回测引擎逐 bar 推进,
# 写成"向量化"会让人照着错误的心智模型理解回测 —— 信号生成走的是向量
# 接口,但成交与权益是按 bar 一步步算的。
ALLOWED_DIAGRAM_DESCRIPTORS = {
    "LangGraph",
    "Event-driven",
    "Tauri",
    "Alpha158 + Alpha101",
}


def _factor_counts() -> tuple[int, int, int]:
    from forgemind.core.factors import (
        factor_count,
        list_alpha101_factors,
        list_alpha158_factors,
    )

    return (factor_count(), len(list_alpha158_factors()), len(list_alpha101_factors()))


def _strategy_count() -> int:
    from forgemind.core.strategies import STRATEGY_REGISTRY
    from forgemind.core.strategies.extended_library import list_strategies

    return len(set(STRATEGY_REGISTRY) | set(list_strategies()))


def _collected_modules(output: str) -> tuple[set[str], dict[str, int]]:
    """从采集输出里取出真正被收集到的测试模块,以及每个模块的用例数。

    pytest 9 的 `-q --collect-only` 打印一棵树,模块写成 <Module xxx.py>,
    用例写成 <Function ...>;更早的版本打印 `tests/xxx.py::test_name`。
    两种都认。

    每个模块的用例数是另一件事:一个文件里一个用例都没有,它照样会被
    收集(出现在树里),但文件数照旧算进"多少个测试文件"里 —— 那种文件
    是虚的,得单独看出来。
    """
    names: set[str] = set()
    counts: dict[str, int] = {}
    current: str | None = None
    for line in output.splitlines():
        m = re.search(r"<Module ([^>]+)>", line)
        if m:
            current = Path(m.group(1).strip()).name
            names.add(current)
            counts.setdefault(current, 0)
            continue
        m = re.match(r"([^:\s]+\.py)::", line.strip())
        if m:
            current = Path(m.group(1)).name
            names.add(current)
            counts.setdefault(current, 0)
            continue
        # 叶子节点的标签随 pytest 版本变:普通函数是 <Function>,异步是
        # <Coroutine>,unittest 的用例方法是 <TestCaseFunction>。全认。
        if current and any(
            tag in line for tag in ("<Function ", "<Coroutine ", "<TestCaseFunction ")
        ):
            counts[current] += 1
    return names, counts


def _measure_test_scale(repo: Path) -> dict | None:
    """实测(文件数, 用例总数, 常规档, 重并发档, 真正被收集到的模块)。

    不是 git 仓就返回 None。
    """
    # 数磁盘上的测试文件,不数 git 跟踪的文件:新加的测试文件在提交之前
    # 就不该被漏掉。跟踪与否是提交状态,不是这个数字该关心的事。
    tests_dir = repo / "tests"
    if not tests_dir.is_dir():
        return None
    files = len(list(tests_dir.glob("test_*.py")))
    # 采集时要**关掉抽样**:CI 里 conftest 会按文件分组抽样重并发用例
    # (默认留十分之一),采到的数就不是声明里那个规模了。
    # 声明的数字对应的是完整规模,测量也得按完整规模来。
    env = {**os.environ, "FORGEMIND_HEAVY_SAMPLE_RATIO": "1"}
    total_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    match = re.search(r"(\d+) tests collected", total_run.stdout)
    if not match:
        return None
    total = int(match.group(1))
    heavy_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-m",
            "heavy",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    heavy_match = re.search(r"(\d+)/(\d+) tests collected", heavy_run.stdout)
    heavy = int(heavy_match.group(1)) if heavy_match else 0
    collected, per_file = _collected_modules(total_run.stdout)
    return {
        "files": files,
        "tests": total,
        "regular": total - heavy,
        "heavy": heavy,
        "collected": collected,
        "per_file": per_file,
    }


def _source_mentions(code: Path, needle: str) -> bool:
    """源码里有没有提到这个关键词(只看 Python 源码,不看依赖清单)。"""
    if not code.is_dir():
        return True
    for path in code.rglob("*.py"):
        if any(part in ("__pycache__", "node_modules", ".git") for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if needle.lower() in text.lower():
            return True
    return False


def local_table_names(code_root: Path) -> set[str]:
    """本地 DuckDB 真正建出来的表名。

    schema 的单一真源是 storage.py(它自己的说明里就这么写着),所以直接
    从那里读 DDL —— 不猜,也不维护第二份名单。名单会漂,DDL 不会。
    """
    src = (code_root / "forgemind/core/data/storage.py").read_text(encoding="utf-8")
    return set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", src))


def main() -> int:
    parser = argparse.ArgumentParser(description="核对 README 的活数字")
    parser.add_argument("readme", type=Path, help="README 路径")
    parser.add_argument("--code", type=Path, default=None, help="源码目录(默认与 README 同级)")
    args = parser.parse_args()

    readme = args.readme.resolve()
    code = (args.code or readme.parent).resolve()
    if str(code) not in sys.path:
        sys.path.insert(0, str(code))

    text = readme.read_text(encoding="utf-8")
    problems: list[str] = []

    # 1) 因子
    m_total = FACTOR_TOTAL.search(text)
    m_split = ALPHA_SPLIT.search(text)
    if m_total or m_split:
        real_total, real_a158, real_a101 = _factor_counts()
        if m_total and int(m_total.group(1)) != real_total:
            problems.append(f"README 写 {m_total.group(1)} 个因子,实际 {real_total} 个")
        if m_split and (int(m_split.group(1)), int(m_split.group(2))) != (real_a158, real_a101):
            problems.append(
                f"README 写 Alpha158 {m_split.group(1)} / Alpha101 {m_split.group(2)},"
                f"实际 {real_a158} / {real_a101}"
            )

    # 2) 策略
    m_strategy = STRATEGY_COUNT.search(text)
    if m_strategy:
        real = _strategy_count()
        if int(m_strategy.group(1)) != real:
            problems.append(f"README 写 {m_strategy.group(1)} 个策略,实际 {real} 个")

    # 3) LLM provider 数量
    m_provider = PROVIDER_COUNT.findall(text)
    if m_provider:
        from forgemind.core.ai.providers import ProviderType

        real = len(list(ProviderType))
        for declared in m_provider:
            if int(declared) != real:
                problems.append(f"README 写 {declared} 个 LLM provider,实际 {real} 个")

    # 4) 文档里点名的 MCP 原语必须真实存在
    from forgemind.mcp.server import ForgeMindMCPServer

    srv = ForgeMindMCPServer()
    real_names = set(srv.tools) | set(srv.resources) | set(srv.prompts)
    # README 里点名一张本地库的真表,那是给用户的交代,不是内部细节漏出来
    # —— 前提是它真的存在。表名从 schema 里读,不用另维护名单。
    table_names = local_table_names(code)
    for token in sorted(set(CODE_TOKEN.findall(text))):
        if token in real_names or token in ALLOWED_OTHER_TOKENS:
            continue
        if token in table_names:
            continue
        problems.append(f"README 里点名的 `{token}` 不是真实的工具/资源/提示词名")

    # 5) 文档里写的 MCP 工具数量要对得上真实数量
    m_mcp_tools = MCP_TOOL_COUNT.search(text)
    if m_mcp_tools:
        from forgemind.mcp.server import ForgeMindMCPServer

        real_tools = len(ForgeMindMCPServer().tools)
        if int(m_mcp_tools.group(1)) != real_tools:
            problems.append(f"README 写 {m_mcp_tools.group(1)} 个 MCP 工具,实际 {real_tools} 个")

    # 6) 文档承诺了宏观数据,宏观源就得真的实现了这些指标
    # 这里只查不依赖可选包的部分 —— akshare 在 [cn] extra 里,常规
    # 流水线没装,拿"能不能取到数"当门禁会误报。真实取数由 verify-live
    # 的实时探针负责。
    if "CN macro" in text or "宏观" in text:
        from forgemind.core.data.sources.extended_sources import MacroDataSource

        schema = MacroDataSource().get_schema()
        for indicator in ("PMI", "CPI", "PPI", "M2_yoy", "10y_yield", "USD_CNY"):
            if indicator not in schema:
                problems.append(f"宏观源少了 {indicator} 指标")
        if "date" not in schema:
            problems.append("宏观源的时间列不叫 date")

    # 7) README 声称用到的技术,源码里必须真的有对应实现。
    # 把逐 bar 推进的引擎说成向量化的,这种话术对不上,用户照着说明
    # 理解代码就会走偏。关键词在源码里找不到,就是只有说法没有实现。
    for label, needle in TECH_CLAIMS.items():
        if label not in text:
            continue
        if not _source_mentions(code, needle):
            problems.append(f"README 里写了 {label},源码里找不到对应的实现({needle})")

    # 8) 架构图里的括号说明必须在白名单内
    section = text.split("Architecture", 1)
    if len(section) == 2:
        block = section[1].split("```", 2)
        if len(block) >= 2:
            for descriptor in re.findall(r"\(([^)]+)\)", block[1]):
                if descriptor not in ALLOWED_DIAGRAM_DESCRIPTORS:
                    problems.append(f"架构图里的说明 ({descriptor}) 不在允许清单里")

    # 9) 测试规模
    m_scale = TEST_SCALE.search(text)
    m_cases = CASE_LINES.findall(text)
    if m_scale and len(m_cases) >= 2:
        declared = (int(m_scale.group(1)), int(m_scale.group(2)), int(m_cases[0]), int(m_cases[1]))
        real = _measure_test_scale(code)
        if real is None:
            problems.append("测不到真实测试规模(不是 git 仓或采集失败)")
        else:
            actual = (real["files"], real["tests"], real["regular"], real["heavy"])
            if declared != actual:
                problems.append(
                    f"README 写 文件 {declared[0]} / 用例 {declared[1]} / "
                    f"常规 {declared[2]} / 重并发 {declared[3]},"
                    f"实际 {actual[0]} / {actual[1]} / {actual[2]} / {actual[3]}"
                )
            # 仓里的测试文件必须真被 pytest 收集 —— 没被收集的文件里那些
            # 用例从来没跑过,而文件数照旧算在里面,数字就虚了。
            tracked = {p.name for p in (code / "tests").glob("test_*.py")}
            missed = sorted(tracked - real["collected"])
            if missed:
                problems.append(
                    f"这些测试文件 pytest 根本没收集(里面的用例一次都没跑):"
                    f"{', '.join(missed[:8])}" + ("…" if len(missed) > 8 else "")
                )
            # 一个都没数出来,说明这次没看懂 pytest 的输出格式 —— 那是
            # "测不到",不是"全是空文件"。把测不到当成缺失,检查就会在
            # pytest 改版那天凭空报出一堆不存在的问题。
            measured = sum(real["per_file"].values())
            empty = sorted(
                name for name in tracked if name in real["per_file"] and real["per_file"][name] == 0
            )
            if measured == 0:
                empty = []
            if empty:
                problems.append(
                    f"这些测试文件里一个用例都没有(文件数是虚的):"
                    f"{', '.join(empty[:8])}" + ("…" if len(empty) > 8 else "")
                )

    if problems:
        print(f"{readme.name} 里的数字与真实情况对不上:")
        for item in problems:
            print(" -", item)
        return 1

    print(f"{readme.name} 里的活数字与真实情况一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
