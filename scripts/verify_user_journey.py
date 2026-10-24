# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""按用户实际会走的路,验证发布出来的包能用。

流水线上每个环节都绿,不代表用户装得上。这条验证完全从用户的角度
出发:从公开的索引页读出下载地址,下载,核对校验值,装进一个干净的
环境,然后真的把命令跑起来、真的握一次 MCP 协议。

任何一步不通,用户那边就是一次失败的安装。

用法:
    python scripts/verify_user_journey.py [--index URL] [--keep]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_INDEX = "https://bin1732.github.io/forgemind-pypi/pypi/simple/forgemind/"
LINK = re.compile(r'href="([^"#]+)(?:#sha256=([0-9a-f]{64}))?"')
MCP_INIT = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "journey-probe", "version": "1"},
        },
    }
)


def _fetch(url: str, timeout: int = 120) -> bytes:
    """取回一个 URL 的内容。

    走 curl 而不是 urllib:有些网络环境里 urllib 的 TLS 握手会被中断,
    curl 反而稳定。用户用什么工具下载,验证就该用什么工具。
    """
    result = subprocess.run(
        ["curl", "-sL", "--max-time", str(timeout), url],
        capture_output=True,
        timeout=timeout + 30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"下载失败: {result.stderr.decode('utf-8', 'replace')[-200:]}")
    return result.stdout


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """跑一条命令。"""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300, **kwargs)


def main() -> int:
    """走一遍用户旅程,返回进程退出码。"""
    parser = argparse.ArgumentParser(description="验证发布出来的包能用")
    parser.add_argument("--index", default=DEFAULT_INDEX, help="公开索引页地址")
    parser.add_argument("--keep", action="store_true", help="保留临时目录")
    args = parser.parse_args()

    problems: list[str] = []

    # 1. 索引页可读,里面有一条指向 wheel 的链接
    print(f"读索引: {args.index}")
    try:
        page = _fetch(args.index).decode("utf-8")
    except Exception as exc:
        print(f"  ✗ 索引页读不到: {exc}", file=sys.stderr)
        return 1
    match = LINK.search(page)
    if not match:
        print("  ✗ 索引页里没有可下载的链接", file=sys.stderr)
        return 1
    url, declared = match.group(1), match.group(2)
    name = url.rsplit("/", 1)[-1]
    print(f"  ✓ 指向 {name}")

    workdir = Path(tempfile.mkdtemp(prefix="forgemind-journey-"))
    try:
        # 2. 下载得到的就是一个真文件
        print("下载构件")
        try:
            payload = _fetch(url)
        except Exception as exc:
            print(f"  ✗ 下载失败: {exc}", file=sys.stderr)
            return 1
        wheel = workdir / name
        wheel.write_bytes(payload)
        print(f"  ✓ 拿到 {len(payload)} 字节")

        # 3. 校验值对得上
        if declared:
            actual = hashlib.sha256(payload).hexdigest()
            if actual != declared:
                problems.append(f"校验值不一致: 声明 {declared},实际 {actual}")
            else:
                print("  ✓ 校验值一致")
        else:
            problems.append("索引里没有校验值")

        # 4. 装进一个干净的环境
        print("装进干净环境")
        venv = workdir / "venv"
        result = _run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)])
        if result.returncode != 0:
            problems.append(f"建虚拟环境失败: {result.stderr[-200:]}")
            print("  ✗ 建虚拟环境失败")
        else:
            pip = venv / "bin" / "pip"
            # 按真实用户的方式装:连依赖一起装。装不上(离线环境)再退回
            # --no-deps,依赖从当前解释器借。
            result = _run(
                [
                    str(pip),
                    "install",
                    "-q",
                    "--retries",
                    "1",
                    "--timeout",
                    "15",
                    str(wheel),
                ]
            )
            borrowed = False
            if result.returncode != 0:
                result = _run(
                    [
                        str(pip),
                        "install",
                        "--no-deps",
                        "--no-index",
                        "-q",
                        str(wheel),
                    ]
                )
                borrowed = True
            if result.returncode != 0:
                problems.append(f"安装失败: {result.stderr[-200:]}")
                print("  ✗ 安装失败")
            else:
                print("  ✓ 安装成功")

                # 5. 命令真的能跑
                exe = venv / "bin" / "forgemind"
                import sysconfig

                purelib = sysconfig.get_paths()["purelib"]
                venv_site = sysconfig.get_path(
                    "purelib", vars={"base": str(venv), "platbase": str(venv)}
                )
                env = {**os.environ}
                if borrowed:
                    # 离线环境里装不了依赖,把当前解释器的依赖路径挂上。
                    # 自己装好的那份必须排在借用路径前面。借用路径里可能有同名的
                    # 旧副本,排在前面会让验证跑到旧代码上,结论就不作数了。
                    env["PYTHONPATH"] = os.pathsep.join(
                        [p for p in (venv_site, os.environ.get("PYTHONPATH", ""), purelib) if p]
                    )
                for label, argv, expect in (
                    ("版本", ["--help"], "backtest"),
                    ("配置", ["info"], "ForgeMind Config"),
                    ("策略列表", ["backtest", "--list-strategies"], "ma_cross"),
                ):
                    result = _run([str(exe), *argv], env=env)
                    output = result.stdout + result.stderr
                    if result.returncode != 0 or expect not in output:
                        problems.append(f"{label}命令异常: {output[-160:]}")
                        print(f"  ✗ {label}")
                    else:
                        print(f"  ✓ {label}")

                # 6. MCP 协议真的能握手
                result = _run([str(exe), "mcp"], input=MCP_INIT + "\n", env=env)
                output = result.stdout
                if '"result"' not in output:
                    problems.append(f"MCP 握手没有结果: {output[-160:]}")
                    print("  ✗ MCP 握手")
                else:
                    print("  ✓ MCP 握手")
    finally:
        if args.keep:
            print(f"临时目录保留在: {workdir}")
        else:
            import shutil

            shutil.rmtree(workdir, ignore_errors=True)

    if problems:
        print("\n用户旅程走不通:")
        for item in problems:
            print(" -", item)
        return 1

    print("\n用户旅程全通: 下载、校验、安装、命令、MCP 协议")
    return 0


if __name__ == "__main__":
    sys.exit(main())
