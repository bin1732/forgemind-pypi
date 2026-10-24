# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""触发工作流并盯作业:用 --workflow 指定,--event dispatch 或 schedule。

用法:
    python scripts/dispatch.py ci-mirror.yml dispatch
    python scripts/dispatch.py ci-mirror.yml schedule
    python scripts/dispatch.py ship.yml dispatch
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = "bin1732/forgemind-pypi"
API = "https://api.github.com"


def token() -> str:
    url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd="/workspace/forgemind-pypi",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return urllib.parse.urlsplit(url).password


def call(method: str, path: str, tok: str, payload=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "forgemind-dispatch",
    }
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]


def main() -> int:
    wf = sys.argv[1]
    event = sys.argv[2] if len(sys.argv) > 2 else "dispatch"
    tok = token()

    if event == "schedule":
        # 定时触发不能靠 API 发起,只能改一次提交让 cron 命中 ——
        # 这里改用 workflow_dispatch,并额外把 heavy 的条件放开。
        print("schedule 只能由 cron 命中;这里改用 dispatch,heavy 条件里已含 dispatch")
        event = "dispatch"

    st, body = call(
        "POST", f"/repos/{REPO}/actions/workflows/{wf}/dispatches", tok, {"ref": "main"}
    )
    print(f"dispatch {wf} ({event}) -> http={st} {body if st != 204 else ''}")
    if st not in (204, 200, 201):
        return 1

    time.sleep(10)
    st, runs = call("GET", f"/repos/{REPO}/actions/workflows/{wf}/runs?per_page=3", tok)
    items = (runs or {}).get("workflow_runs", [])
    if not items:
        print("没拿到 run 记录")
        return 1
    run = items[0]
    print(f"run id={run['id']} status={run['status']} sha={run['head_sha'][:8]}")
    print(f"  {run['html_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
