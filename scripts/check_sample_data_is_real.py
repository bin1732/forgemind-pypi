#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对内置的样例行情是不是**真实**的 600519 日线。

`forgemind demo` 的核心承诺是"包内置的是真实历史行情,不是随机数凑的"。
这条承诺原先只有一句出处说明(腾讯财经前复权日线,抓取于某天)—— 说得
清楚,但没人能核。文档里写"真实"却不给机器核的办法,读者只能选择相信。

这里把它变成可核的:从上游公开行情接口取同一段日线,与包里的那份逐行比对。

判据分两层,强度不一样:

- **日期序列必须完全一致** —— 一根不多一根不少。这是结构性的事实,
  编造不出来。
- **成交量必须完全一致** —— 复权只调价格,不动成交量。所以成交量对得上
  ⇒ 这一串确实是那天的真实成交。
- **收盘价允许有偏差** —— 前复权价会因分红除权而重算,过几个月与抓取
  当天不完全一样是正常的,给 0.5% 的容差;偏差超过它,说明要么数据被改过,
  要么口径变了,两件都要人来定。

用法:
    python scripts/check_sample_data_is_real.py [--csv <路径>] [--tolerance 0.005]

上游取不到时**报错退出**,不当作通过:这条判据的全部价值就在"真的去取一次"。
确实需要离线跑时,设 FORGEMIND_SKIP_UPSTREAM_CHECK=1 显式跳过。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO / "forgemind" / "data" / "sample_600519_2024.csv"
# 腾讯财经的公开前复权日线接口
UPSTREAM = (
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600519,day,{start},{end},400,qfq"
)


def fetch_upstream(start: str, end: str, timeout: int = 60, attempts: int = 3) -> list[dict]:
    """取上游的日线,返回 [{date, open, close, high, low, volume}]。

    外部接口偶尔会慢或抖一下 —— 重试几次再放弃。持久取不到仍然算失败:
    这条判据的全部价值就在"真的去取一次",取不到就说取不到。
    """
    import time

    url = UPSTREAM.format(start=start, end=end)
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "forgemind-sample-check"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8", "replace"))
            break
        except Exception as exc:  # noqa: BLE001 — 重试几次再放弃
            last = exc
            if attempt < attempts - 1:
                time.sleep(5 * (attempt + 1))
    else:
        raise last if last else RuntimeError("取不到上游行情")

    node = (body.get("data") or {}).get("sh600519") or {}
    rows = node.get("qfqday") or node.get("day") or []
    out = []
    for row in rows:
        # 腾讯的字段顺序:日期 开 收 高 低 量
        out.append(
            {
                "date": row[0],
                "open": float(row[1]),
                "close": float(row[2]),
                "high": float(row[3]),
                "low": float(row[4]),
                "volume": float(row[5]),
            }
        )
    return out


def read_csv(path: Path) -> list[dict]:
    import csv

    with path.open(encoding="utf-8", newline="") as f:
        return [
            {
                "date": row["date"],
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": float(row["volume"]),
            }
            for row in csv.DictReader(f)
        ]


def compare(local: list[dict], upstream: list[dict], tolerance: float) -> list[str]:
    """返回不一致的说明;空列表 = 一致。"""
    problems: list[str] = []
    local_dates = [r["date"] for r in local]
    upstream_dates = [r["date"] for r in upstream]
    if local_dates != upstream_dates:
        only_local = sorted(set(local_dates) - set(upstream_dates))
        only_up = sorted(set(upstream_dates) - set(local_dates))
        problems.append(
            f"日期序列不一致(本地 {len(local_dates)} 根 / 上游 {len(upstream_dates)} 根);"
            f"只有本地有:{only_local[:5]};只有上游有:{only_up[:5]}"
        )
        return problems

    up_by_date = {r["date"]: r for r in upstream}
    checked = 0
    for row in local:
        up = up_by_date[row["date"]]
        if row["volume"] != up["volume"]:
            problems.append(
                f"{row['date']} 成交量对不上:本地 {row['volume']} / 上游 {up['volume']}"
                " —— 复权只调价格不动成交量,这一项对不上就不是那天的真实成交"
            )
        else:
            checked += 1
        base = abs(up["close"]) or 1.0
        drift = abs(row["close"] - up["close"]) / base
        if drift > tolerance:
            problems.append(
                f"{row['date']} 收盘价偏差 {drift:.4%}(超过容差 {tolerance:.4%}):"
                f"本地 {row['close']} / 上游 {up['close']}"
            )
    if len(problems) > 12:
        extra = len(problems) - 12
        problems = problems[:12] + [f"… 还有 {extra} 处"]
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="核对内置样例行情与上游真实行情一致")
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="样例 CSV 路径")
    ap.add_argument("--tolerance", type=float, default=0.005, help="收盘价允许的偏差")
    args = ap.parse_args()

    if os.environ.get("FORGEMIND_SKIP_UPSTREAM_CHECK") == "1":
        print("按环境变量跳过上游核对(这次没有验证内置数据是不是真实的)")
        return 0

    path = Path(args.csv)
    if not path.is_file():
        print(f"找不到样例文件:{path}", file=sys.stderr)
        return 1
    local = read_csv(path)
    if not local:
        print(f"样例文件里没有数据:{path}", file=sys.stderr)
        return 1

    start, end = local[0]["date"], local[-1]["date"]
    try:
        upstream = fetch_upstream(start, end)
    except Exception as exc:  # noqa: BLE001 — 取不到就是取不到,不能当通过
        print(
            f"取不到上游行情({type(exc).__name__}: {exc})—— 这次没有验证内置数据"
            " 是不是真实的。真要离线跑,设 FORGEMIND_SKIP_UPSTREAM_CHECK=1",
            file=sys.stderr,
        )
        return 1

    problems = compare(local, upstream, args.tolerance)
    if problems:
        print("内置样例与上游真实行情对不上:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(
        f"内置样例就是真实的 600519 日线:{len(local)} 根"
        f"({start} → {end}),日期序列与成交量逐行一致,收盘价在 {args.tolerance:.2%} 容差内"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
