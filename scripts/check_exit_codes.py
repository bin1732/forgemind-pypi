#!/usr/bin/env python3
# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对 README 里的退出码表与命令的真实退出码一致。

表是对用户的承诺:看到某个退出码,就知道发生了什么、该做什么。表与实际
行为分家,这张表就只剩误导作用。

真出现过:表里写着"用户中断 = 1",实测是 130;写着"agent 审批拒绝 = 5+",
实测是 2 —— 而 2 那一行写的是"资源类",两个场景挤在同一个码上,读的人
无从判断该做什么。

所以这张表由机器守着:命令真跑一遍,退出码与表对不上就报错。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: (说明, 命令, 期望退出码, 怎么造这个场景)。造不出来的场景就别写进
#: 表里 —— 那正是这张表要治的病:写着"磁盘满 = 4"却没人验过。
#: setup 为 None 表示不需要特殊环境。
#:
#: 场景怎么造(都是真的,不是 mock):
#:   locked        —— 另一个真进程占着同一个库文件
#:   write_full    —— 子进程的写文件上限被压到 4 KB,写不进去
#:   timeout_upstream —— 注入一个 import 就抛超时的假上游模块
PROBES: tuple[tuple[str, tuple[str, ...], int, str | None], ...] = (
    ("正常完成", ("info",), 0, None),
    ("正常完成", ("signal",), 0, None),
    ("argparse 用法错误", ("backtest", "--bogus-flag"), 2, None),
    ("策略名不存在", ("backtest", "--strategy", "NoSuchStrategyAnywhere"), 2, None),
    ("这个命令喂不了该策略", ("backtest", "--strategy", "MaxSharpe"), 2, None),
    ("没给子命令", (), 2, None),
    ("策略要额外参数", ("backtest", "--strategy", "PairsTrading"), 2, None),
    (
        "数据源没装,一条没取到",
        ("etl", "--symbols", "600519", "--start", "2024-01-01", "--end", "2024-01-31"),
        3,
        None,
    ),
    (
        "上游无响应",
        ("etl", "--symbols", "600519", "--start", "2024-01-01", "--end", "2024-01-31"),
        3,
        "timeout_upstream",
    ),
    (
        "非交互模式未审批",
        (
            "agent",
            "--symbol",
            "600519.SH",
            "--cash",
            "100000",
            "--position-qty",
            "5",
            "--position-price",
            "1600",
        ),
        2,
        None,
    ),
    (
        "本地库被另一个进程占着",
        (
            "backtest",
            "--symbol",
            "600519",
            "--start",
            "2024-01-01",
            "--end",
            "2024-06-30",
        ),
        4,
        "locked",
    ),
    (
        "存储写不进去",
        (
            "backtest",
            "--symbol",
            "600519",
            "--start",
            "2024-01-01",
            "--end",
            "2024-06-30",
        ),
        4,
        "write_full",
    ),
    (
        # 这条命令自己不管资源类的错,交给命令行的统一兜底 —— 所以
        # 它罩的是兜底那条路。少了兜底,这一条会红。
        "存储写不进去(走统一兜底)",
        ("signal", "--symbol", "600519"),
        4,
        "write_full",
    ),
)

# 表里该有哪些退出码。
#
# 码集合放在这里,措辞放在 README 里 —— 各管一处,不用把两边的散文抄成
# 两份。130(用户中断)在这里但不在探针里:它是 Python 对未捕获
# KeyboardInterrupt 的标准退出码,不是某个命令自己定的。
#
# 1 也不在探针里:它要 PM 节点已经跑过(得先跑一遍 agent 再重放)。
#
# 4 现在**在**探针里了 —— 以前这条被写成"磁盘真的满(ENOSPC)造不出来",
# 于是表里"资源类"那一行从来没人验过,命令实际给出别的码也没人知道。
# 造不出来的说法要靠"另找一个真能造出来的法子"推翻,不能就这么信了:
# 写不进去可以用压写上限来造,库被占着可以用另一个真进程来造。
EXPECTED_CODES = (0, 1, 2, 3, 4, 130)

_TABLE_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", re.M)


def documented_codes(readme: Path) -> dict[int, str]:
    """读出 README 表里记的退出码与类别。"""
    text = readme.read_text(encoding="utf-8")
    start = text.find("## 🛑 错误码速查表")
    if start < 0:
        raise SystemExit("README 里找不到错误码速查表")
    end = text.find("\n##", start + 10)
    section = text[start : end if end > 0 else len(text)]
    out: dict[int, str] = {}
    for code, category in _TABLE_ROW.findall(section):
        out[int(code)] = category
    return out


def looks_like_missing_dependency(output: str) -> bool:
    """这段输出是不是"命令没跑起来,环境里缺东西"。

    命令压根没跑起来,与"退出码不对"是两回事:前者是环境的毛病,后者才
    是行为与表分家。混在一起报,会把环境的毛病说成行为不符。
    """
    return "ModuleNotFoundError" in output or "No module named" in output


def _lock_holder(db_path: Path):
    """起一个真进程占着这个库文件。返回那个进程。"""
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import duckdb, sys, time\n"
                "con = duckdb.connect(sys.argv[1])\n"
                "print('held', flush=True)\n"
                "time.sleep(600)\n"
            ),
            str(db_path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )


def _fake_upstream_dir(root: Path) -> Path:
    """造一个"import 就抛超时"的上游模块目录。

    真上游无响应时,代码走的就是这条路:取数调用超时 → 归类成上游类。
    注入一个假模块,比等一个真的网络超时既快又稳定 —— 而走的是同一段
    代码,不是 mock。
    """
    pkg = root / "fake_upstream"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "akshare.py").write_text(
        "raise TimeoutError('上游行情源无响应')\n",
        encoding="utf-8",
    )
    return pkg


def run_probe(
    argv: tuple[str, ...],
    db_path: Path,
    setup: str | None = None,
    extra_path: Path | None = None,
) -> tuple[int, str]:
    """跑一个命令,返回 (退出码, 失败时的输出)。"""
    env = dict(os.environ)
    env["FORGEMIND_DUCKDB_PATH"] = str(db_path)
    env["FORGEMIND_LOG_LEVEL"] = "ERROR"
    env["FORGEMIND_NONINTERACTIVE"] = "1"
    if extra_path is not None:
        env["PYTHONPATH"] = os.pathsep.join(
            [str(extra_path), env.get("PYTHONPATH", "")],
        ).rstrip(os.pathsep)
    preexec = None
    if setup == "write_full":
        # 子进程能写的文件不超过 4 KB —— 磁盘满/配额用完时的样子。
        # 真去填满磁盘做不到(要 root),压写上限是同一类故障:写不进去。
        def preexec() -> None:  # noqa: F811 — 闭包,名字在下面才用
            import resource

            resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))

    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
        preexec_fn=preexec,
    )
    return result.returncode, (result.stdout + result.stderr)[-400:]


def probe_with_setup(
    label: str,
    argv: tuple[str, ...],
    db_path: Path,
    setup: str | None,
    tmp_root: Path,
) -> tuple[int, str]:
    """按场景造好环境,再跑探针。"""
    if setup == "locked":
        holder = _lock_holder(db_path)
        assert holder.stdout is not None
        holder.stdout.readline()  # 等它真的握住锁
        try:
            return run_probe(argv, db_path, setup=setup)
        finally:
            holder.terminate()
            try:
                holder.wait(timeout=10)
            except subprocess.TimeoutExpired:
                holder.kill()
    if setup == "timeout_upstream":
        return run_probe(
            argv,
            db_path,
            setup=setup,
            extra_path=_fake_upstream_dir(tmp_root),
        )
    return run_probe(argv, db_path, setup=setup)


def main() -> int:
    parser = argparse.ArgumentParser(description="核对 README 的退出码表")
    parser.add_argument(
        "readme",
        nargs="?",
        type=Path,
        default=REPO_ROOT / "README.md",
        help="README 路径",
    )
    args = parser.parse_args()

    table = documented_codes(args.readme)
    if not table:
        print("README 的错误码表是空的", file=sys.stderr)
        return 1

    problems: list[str] = []

    # 表里的码集合要与该有的码一致:多一行少一行都不行。
    missing = [c for c in EXPECTED_CODES if c not in table]
    extra = [c for c in table if c not in EXPECTED_CODES]
    for code in missing:
        problems.append(f"表里缺退出码 {code}")
    for code in extra:
        problems.append(f"表里多了退出码 {code}(该有的码是 {list(EXPECTED_CODES)})")

    with tempfile.TemporaryDirectory(prefix="forgemind-exit-codes-") as tmp:
        tmp_root = Path(tmp)
        for index, (label, argv, expected, setup) in enumerate(PROBES):
            # 每个探针用自己的库文件:共用一个的话,前一个探针已经把库
            # 建好了,后一个探针的写入量变小,"写不进去"就造不出来了 ——
            # 场景没真被造出来,探针却"通过"了。
            db = tmp_root / f"probe_{index}.db"
            actual, output = probe_with_setup(label, argv, db, setup, tmp_root)
            # 命令压根没跑起来,与"退出码不对"是两回事:前者是环境缺东西,
            # 混在一起报,会把环境的毛病说成行为不符。
            if looks_like_missing_dependency(output):
                problems.append(
                    f"{label}({argv[0]}): 命令没跑起来,环境里缺依赖 —— {output.strip()[-200:]}"
                )
                continue
            if actual != expected:
                problems.append(f"{label}({argv[0]}): 实际退出码 {actual},表里写的是 {expected}")
                continue
            if expected not in table:
                problems.append(f"退出码 {expected}({label})没有出现在 README 的表里")
                continue
            print(f"  ✓ {label}: 退出码 {actual} —— {table.get(expected, '')}")

    if problems:
        print("退出码与 README 的表对不上:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"退出码与 README 的表一致({len(PROBES)} 条)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
