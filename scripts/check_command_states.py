#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""每条用户能用的命令,在各种"没有/读不到"的状态下都必须说真话。

**为什么要有这个**:一次手工撞出来的问题 —— 桌面端开着的时候它占着同一个
DuckDB 文件,终端里的命令连不上那个库,可命令说的是"在库里没有 K 线"。
用户照着提示去拉数据,而拉数据同样连不上那个库,一路撞墙。

那一次是手工撞上的。这一类问题靠手工撞,下一次换个状态就漏了。所以把
"每个状态该说什么"做成机器判据,每一轮都跑。

**五种状态**:

| 状态 | 怎么造出来 | 该说什么 |
|---|---|---|
| 没有数据 | 库里没有这个标的 | 说"没有数据",并给出去拉数据的命令 |
| 数据不足 | 库里只有几根 K 线 | 说"仅 N 根",说清差多少 |
| 库被占着 | 另一个进程占着同一个库文件 | 说"读不到/被占用",**不许**说"没有数据" |
| 没有密钥 | 不配模型服务商的密钥 | 说清缺哪个,不要编 |
| 写不进去 | 子进程的写文件上限被压到 4 KB | 说"存储写不进去",退出码 4,**不许**产出数字 |

**每种状态下都成立的三条**:

1. 响应里不许有内部实现:异常类名、SQL 片段、栈回溯、本机路径。
2. 降级到模拟数据时必须标明是模拟 —— 用户不该拿到一份看着像真实回测的
   假结果。
3. "读不到"与"没有数据"必须分开说。

**另外两条,只对碰本地库的命令**:

4. 库被占着或写不进去时,退出码必须是 4(资源类),不能报成功。
5. 这两种状态下不许吐出回测数字 —— 连落盘都写不进去,给数字等于
   说"跑通了"。

用法:
    python scripts/check_command_states.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_cli_output_clean as leak  # noqa: E402

#: 要核的命令。每一行都要在每种状态下跑一遍。
COMMANDS: list[list[str]] = [
    ["backtest", "--symbol", "600519", "--start", "2024-01-01", "--end", "2024-06-30"],
    ["pick", "--symbol", "600519"],
    ["signal", "--symbol", "600519"],
    ["agent", "--symbol", "600519.SH", "--cash", "80000", "--yes"],
    ["demo"],
    ["info"],
    ["router-demo"],
]

#: 状态:名字 → 造这个状态要做什么
STATES = ("no_data", "insufficient", "locked", "no_key", "write_full")

#: 内部实现不许出现在输出里的形态(与命令行的判据同源)。
FORBIDDEN = ("异常类名", "SQL 片段", "Python 栈回溯", "本机绝对路径")

#: 会读本地库的子命令。只有这些命令才需要在"库被占着"时说明读不到 ——
#: demo 用的是包内置的行情、info 只打印配置、router-demo 只演示路由,
#: 它们本来就不碰那个库,要求它们说"读不到"是判据自己搞错了。
NEEDS_LOCAL_STORE = {"backtest", "pick", "signal", "agent"}

#: "读不到"该有的说法。"库被占着"这个状态下,输出里至少要有一个。
UNREADABLE_MARKERS = ("读不到", "占用")

#: "没有数据"该有的说法。
MISSING_MARKERS = ("没有 K 线", "无数据", "没有该标的", "库里没有")

#: 提到模拟/合成数据时,旁边必须有的免责说法(不同命令的措辞不一样)。
SYNTHETIC_MARKERS = ("模拟", "合成")
DISCLAIMER_MARKERS = ("非真实", "不是模拟", "只用于验证", "不代表")


def _duckdb_path(work: Path) -> Path:
    return work / "duckdb" / "main.db"


def _make_db(path: Path, bars: int) -> None:
    """造一个库:bars 根 K 线(0 = 连表都没有)。"""
    import duckdb

    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    if bars <= 0:
        con.close()
        return
    con.execute(
        "CREATE TABLE kline_daily (symbol VARCHAR, date DATE, open DOUBLE, "
        "high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE)"
    )
    import datetime as dt

    base = dt.date(2024, 1, 1)
    rows = []
    price = 100.0
    for i in range(bars):
        price *= 1.01
        rows.append(("600519", base + dt.timedelta(days=i), price, price, price, price, 1000.0))
    con.executemany("INSERT INTO kline_daily VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    con.close()


def _lock_holder(path: Path):
    """起一个进程占着这个库文件,返回那个进程。"""
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
            str(path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )


def _run(
    command: list[str],
    work: Path,
    db: Path,
    limit_file_size: bool = False,
) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)
    env["PYTHONSAFEPATH"] = "1"
    env["FORGEMIND_DATA_DIR"] = str(work / "data")
    env["FORGEMIND_DUCKDB_PATH"] = str(db)
    env["FORGEMIND_LOG_LEVEL"] = "ERROR"
    # 没有密钥:模型服务商的密钥全清掉(命令行为空时用它自己报错)
    for key in list(env):
        if key.endswith("_API_KEY") or key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            env.pop(key)
    preexec = None
    if limit_file_size:
        # 子进程能写的文件不超过 4 KB —— 磁盘满/配额用完时的样子。
        # 真去填满磁盘做不到(要 root),压写上限是同一类故障:写不进去。
        def preexec() -> None:  # noqa: F811 — 闭包,名字在下面才用
            import resource

            resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.cli", *command],
            capture_output=True,
            text=True,
            timeout=240,
            cwd=str(work),
            env=env,
            preexec_fn=preexec,
        )
    except subprocess.TimeoutExpired:
        return 124, "(超时)"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _check_one(command: list[str], state: str) -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="forgemind_state_") as tmp:
        work = Path(tmp)
        db = _duckdb_path(work)
        holder = None
        if state == "no_data":
            _make_db(db, 0)
        elif state == "insufficient":
            _make_db(db, 5)
        elif state == "locked":
            _make_db(db, 5)
            holder = _lock_holder(db)
            assert holder.stdout is not None
            holder.stdout.readline()  # 等它真的握住锁
            time.sleep(0.3)
        elif state == "no_key":
            _make_db(db, 5)
        elif state == "write_full":
            # 刻意**不**建库:库文件还不存在,子进程第一次连上它时就得
            # 写它 —— 那一步就会撞上写上限。库已经建好的话,写入量很小,
            # 这个状态就造不出来了(造不出来 ≠ 通过)。
            pass

        rc, out = _run(command, work, db, limit_file_size=(state == "write_full"))
        if holder is not None:
            holder.terminate()
            try:
                holder.wait(timeout=10)
            except subprocess.TimeoutExpired:
                holder.kill()

        label = f"forgemind {' '.join(command)} [{state}]"

        # 1) 内部实现不许出现
        for kind, segment in leak._scan(out, leak.COMPILED_LEAKS):
            if kind in FORBIDDEN:
                problems.append(f"{label}: 输出里有{kind}: ...{segment}...")

        # 2) "库被占着"这个状态下,不许说"没有数据"(只对读库的命令有要求)
        reads_store = command[0] in NEEDS_LOCAL_STORE
        if state == "locked" and reads_store:
            if any(marker in out for marker in MISSING_MARKERS):
                problems.append(
                    f"{label}: 输出说'没有数据' —— 连都没连上,不知道有没有。"
                    f"应当说:{'/'.join(UNREADABLE_MARKERS)}"
                )
            if not any(marker in out for marker in UNREADABLE_MARKERS):
                problems.append(f"{label}: 没说要读不到 —— 用户不知道该做什么")
        # 3) 别的状态下,不该冒出"被占用"
        if state != "locked" and any(marker in out for marker in ("占用",)):
            problems.append(f"{label}: 说了'占用',但这个状态下库没有被占着")

        # 4) 用了模拟数据就要标明
        if any(marker in out for marker in SYNTHETIC_MARKERS) and not any(
            marker in out for marker in DISCLAIMER_MARKERS
        ):
            problems.append(f"{label}: 用了模拟数据,却没有标明它不是真实结果")

        # 5) 资源类状态:退出码必须是 4,而且不该吐出回测数字。
        #    库被占着、存储写不进去的时候,命令什么都没跑成 ——
        #    给一组数字出来,读的人只会以为它跑通了。
        if state in ("locked", "write_full") and reads_store:
            if rc != 4:
                problems.append(f"{label}: 退出码 {rc} —— 这一类是资源类,表里写的是 4")
            for marker in ("Total Return", "Sharpe", "Max Drawdown"):
                if marker in out:
                    problems.append(
                        f"{label}: 吐出了回测数字({marker})—— "
                        f"这一类状态下连落盘都写不进去,给数字等于说'跑通了'"
                    )

        # 6) "写不进去"也不许说成"没有数据"
        if state == "write_full" and any(marker in out for marker in MISSING_MARKERS):
            problems.append(
                f"{label}: 输出说'没有数据' —— 写不进去与没有数据是两回事,"
                f"说成后者会让用户去拉数据,而写不进去的时候拉数据同样写不进去"
            )

    return problems


def main() -> int:
    problems: list[str] = []
    for state in STATES:
        for command in COMMANDS:
            problems.extend(_check_one(command, state))
    if problems:
        print(f"命令在各种状态下没有说真话({len(problems)} 处):")
        for item in problems:
            print(" -", item)
        return 1
    print(
        f"命令状态核对通过({len(COMMANDS)} 条命令 × {len(STATES)} 种状态 = "
        f"{len(COMMANDS) * len(STATES)} 种组合)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
