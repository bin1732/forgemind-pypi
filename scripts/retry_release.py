#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""发布被平台的 macOS 队列卡住时,一条命令把它补出来。

**问题**:发布要构建三个平台的独立二进制。macOS 的 runner 池子小,而且按
组织配额限流 —— 排不上的时候,平台在 15 分钟整把那个作业取消掉(作业
runner_name 为空、steps 为 0)。发布于是没发出去:构件不齐,发布不进行,
线上索引仍指着上一次完整发布(这一点是对的,不该有半发布的产物)。

**为什么不能自己重试**:作业是被平台杀掉的,作业里的任何重试逻辑都跟着
一起没了。恢复只能从**运行**这一层做:把失败的作业重跑一遍。已经成功的
那些作业的构件还留在这次运行里,所以只要 macOS 那个补上,发布就能继续。

用法:
    python scripts/retry_release.py                 # 找最近一次失败的发布并补跑
    python scripts/retry_release.py --run 12345     # 指定那次运行
    python scripts/retry_release.py --wait          # 等它跑完,报最终结论
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
DEFAULT_REPO = "bin1732/forgemind-pypi"
#: 发布的流水线文件名
PUBLISH_WORKFLOW = "ship.yml"


def request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    """调 GitHub API。返回解析后的 JSON。"""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "forgemind-retry-release",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise SystemExit(f"{method} {url} 失败({exc.code}):{detail}") from exc


def token_from_env() -> str:
    """能读公开仓的凭据。"""
    for key in ("GITHUB_TOKEN", "GH_PAT"):
        value = os.environ.get(key)
        if value:
            return value
    raise SystemExit("没有凭据:设 GITHUB_TOKEN 或 GH_PAT 再跑(读公开仓的运行记录、补跑作业都要它)")


def latest_failed_publish_run(repo: str, token: str) -> dict:
    """最近一次失败的发布运行。"""
    url = f"{API}/repos/{repo}/actions/workflows/{PUBLISH_WORKFLOW}/runs?per_page=20"
    data = request("GET", url, token)
    for run in data.get("workflow_runs", []):
        if run.get("conclusion") == "failure":
            return run
    raise SystemExit("没有失败的发布运行 —— 不用补跑")


def is_on_main_head(repo: str, token: str, run: dict) -> bool:
    """这次运行的提交还在 main 的头上吗?

    补跑会把**那次运行**的构件发布出去。如果那次运行的提交已经被后来的提交
    取代(通常是因为它自己有问题、被改掉重推了),补跑等于把旧版本再发一遍
    —— 线上索引会指向一个已经不该发的提交。

    所以默认拒绝,除非显式 --force。
    """
    head = request("GET", f"{API}/repos/{repo}/commits/main", token)
    return str(head.get("sha", "")) == str(run.get("head_sha", ""))


def failed_jobs(repo: str, token: str, run_id: int) -> list[dict]:
    """这次运行里失败的作业。"""
    url = f"{API}/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    data = request("GET", url, token)
    return [j for j in data.get("jobs", []) if j.get("conclusion") not in ("success", "skipped")]


def rerun_failed(repo: str, token: str, run_id: int) -> None:
    """把这次运行失败的作业重跑一遍。"""
    request("POST", f"{API}/repos/{repo}/actions/runs/{run_id}/rerun-failed-jobs", token, {})


def run_state(repo: str, token: str, run_id: int) -> tuple[str, str | None]:
    """这次运行的状态与结论。"""
    url = f"{API}/repos/{repo}/actions/runs/{run_id}"
    data = request("GET", url, token)
    return data.get("status", ""), data.get("conclusion")


def published_version(repo: str, token: str) -> str:
    """线上清单里的发布版本。"""
    url = f"{API}/repos/{repo}/contents/releases/builds/manifest.json"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.raw",
            "User-Agent": "forgemind-retry-release",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return str(json.load(resp).get("published_version", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="补跑被平台取消的发布作业")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="发布面那个仓(owner/repo)")
    parser.add_argument("--run", type=int, default=None, help="要补跑的那次运行运行编号")
    parser.add_argument("--wait", action="store_true", help="等它跑完,报最终结论")
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使那次运行的提交已经不在 main 头上也补跑(会把那个旧版本发一遍)",
    )
    parser.add_argument("--timeout", type=int, default=3600, help="等待上限(秒)")
    args = parser.parse_args()

    token = token_from_env()
    if args.run:
        run_id = args.run
        run = request("GET", f"{API}/repos/{args.repo}/actions/runs/{run_id}", token)
        print(f"指定的运行 #{run_id}:{run.get('head_sha', '')[:8]} 结论 {run.get('conclusion')}")
    else:
        run = latest_failed_publish_run(args.repo, token)
        run_id = run["id"]
        print(f"最近一次失败的发布:运行 #{run_id} 提交 {run.get('head_sha', '')[:8]}")

    jobs = failed_jobs(args.repo, token, run_id)
    if not jobs:
        print("这次运行没有失败的作业 —— 不用补跑")
        return 0

    if not args.force and not is_on_main_head(args.repo, token, run):
        print("这次运行的提交已经不在 main 的头上了 —— 补跑会把那个旧提交再发一遍。")
        print(f"  那次运行:{run.get('head_sha', '')[:8]}")
        print(
            f"  main 头:{(request('GET', f'{API}/repos/{args.repo}/commits/main', token).get('sha') or '')[:8]}"
        )
        print("确认要发那个旧版本,就加 --force。")
        return 1
    for job in jobs:
        print(f"  失败的作业:{job.get('name')} ({job.get('conclusion')})")

    before = published_version(args.repo, token)
    rerun_failed(args.repo, token, run_id)
    print(f"已触发补跑。补跑前线上版本:{before}")

    if not args.wait:
        print("加 --wait 可以在这里等它跑完并报最终结论。")
        return 0

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        status, conclusion = run_state(args.repo, token, run_id)
        if status == "completed":
            after = published_version(args.repo, token)
            print(f"这次运行跑完了,结论 {conclusion};线上版本:{before} → {after}")
            if conclusion == "success" and after != before:
                print("发布补上了 ✓")
                return 0
            print("没有发布出去 —— 看这次运行的作业日志找原因。")
            return 1
        time.sleep(30)
    print("等待超时。去看那次运行的作业日志。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
