# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""Tauri 桌面端的 Python sidecar 通路

`python -m forgemind.api.main` 起来后**立即退出**——
  * 忽略 --host/--port,一律绑 settings 里的端口。Tauri 传 8008,
    服务却绑 8000,桌面端所有请求都打不通
  * 同时写了 `uvicorn.run(app, reload=True)`,传对象时无法启用 reload,
    uvicorn 打印警告后直接退出

后果:桌面端 UI 能开,但任何数据都拿不到 —— 整个客户端是死的,
该验证只检查二进制能启动、源码里有没有这些字符串,从未真跑过。

本文件按 Tauri 的**原始参数**真起 sidecar,再走它实际调用的两个端点。
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _env():
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT) + os.pathsep + e.get("PYTHONPATH", "")
    e["FORGEMIND_API_SECRET_KEY"] = "a" * 32
    return e


def _start(port: int) -> subprocess.Popen:
    # 输出必须留住:sidecar 秒退时 DEVNULL 会把唯一的线索一起丢掉,
    # 失败只会剩一句"未就绪",无法判断是没起来还是参数没生效
    proc = subprocess.Popen(
        [sys.executable, "-m", "forgemind.api.main",
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=_env(), cwd="/tmp", text=True,
    )
    return proc


def _drain(proc: subprocess.Popen) -> str:
    """取走已产生的输出(不阻塞等待进程结束)"""
    if proc.stdout is None:
        return ""
    if proc.poll() is None:
        # 进程还活着:置为非阻塞后能读到"目前为止"的日志,
        # 超时场景下这是唯一线索,不能因为没退出就什么都拿不到
        try:
            import fcntl
            fd = proc.stdout.fileno()
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            return (proc.stdout.read() or "") + ""
        except Exception:
            return ""
    try:
        return proc.stdout.read() or ""
    except Exception:
        return ""


def _stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def _wait_health(proc: subprocess.Popen, port: int, tries: int = 120):
    """等服务就绪;若进程先退出则立即失败并说明原因

    60 秒预算:低内存机器上冷启动要拉起 FastAPI + langchain,22 秒不够。
    机器慢不等于产品坏,但真失败必须能从输出看出原因。
    """
    url = f"http://127.0.0.1:{port}/health"
    for _ in range(tries):
        if proc.poll() is not None:
            pytest.fail(
                f"sidecar 进程 {proc.returncode} 秒退 —— 桌面端永远拿不到数据\n"
                f"进程输出:\n{_drain(proc)[-2000:]}")
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return json.loads(r.read())
        except Exception:
            time.sleep(0.5)
    pytest.fail(
        f"sidecar 未在 {tries * 0.5:.0f}s 内就绪(端口 {port})。"
        f"进程存活={proc.poll() is None},输出:\n{_drain(proc)[-2000:]}")


class TestDesktopSidecarStarts:
    def test_module_entrypoint_accepts_host_and_port(self):
        """Tauri 就是用这个命令拉 sidecar;参数被忽略 = 桌面端拿不到数据"""
        port = _free_port()
        proc = _start(port)
        try:
            d = _wait_health(proc, port)  # 不就绪时自行 pytest.fail
            assert d["status"] == "ok", d
        finally:
            _stop(proc)

    def test_production_entrypoint_never_forces_reload(self):
        """生产入口不能硬编码 reload=True —— 传 app 对象时 uvicorn 会直接退出

        只看**可执行代码**:说明性注释里允许出现这段历史,
        否则断言会被注释本身命中而失去意义。
        """
        import ast

        tree = ast.parse((ROOT / "forgemind/api/main.py").read_text(encoding="utf-8"))
        # 只看真实 AST 节点,注释和 docstring 天然被排除
        reload_true = False
        reload_from_arg = False
        import_string = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            fname = getattr(fn, "attr", getattr(fn, "id", ""))
            if fname != "run":
                continue
            # uvicorn.run(app) 的 app 可以是位置参数或关键字参数
            if node.args and isinstance(node.args[0], ast.Constant):
                import_string = ":" in str(node.args[0].value)
            for kw in node.keywords:
                if kw.arg == "app" and isinstance(kw.value, ast.Constant):
                    import_string = ":" in str(kw.value.value)
                if kw.arg == "reload":
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        reload_true = True
                    if isinstance(kw.value, ast.Attribute) and kw.value.attr == "reload":
                        reload_from_arg = True
                if kw.arg == "app" and isinstance(kw.value, ast.Constant):
                    import_string = ":" in str(kw.value.value)
        assert not reload_true, "生产入口硬编码 reload=True 会让 uvicorn 直接退出"
        assert reload_from_arg, "reload 应由显式参数控制"
        assert import_string, "reload 需配合 import string"

    def test_mcp_endpoint_the_desktop_uses(self):
        """Tauri 的 mcp_call_tool 打的就是 /mcp/tools/call,这里真打一次"""
        port = _free_port()
        proc = _start(port)
        try:
            _wait_health(proc, port)  # 不就绪时自行 pytest.fail
            url = f"http://127.0.0.1:{port}/mcp/tools/call"
            payload = json.dumps(
                {"name": "search_features", "arguments": {"query": "momentum"}}).encode()
            got = None
            for _ in range(20):
                req = urllib.request.Request(
                    url, data=payload,
                    headers={"Content-Type": "application/json"}, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=8) as r:
                        got = json.loads(r.read())
                    break
                except Exception:
                    time.sleep(0.5)
            assert got, "MCP 端点无响应"
            assert "result" in got, got
            body = json.loads(got["result"]["content"][0]["text"])
            assert body["total"] > 100, f"因子数异常: {body['total']}"
        finally:
            _stop(proc)

    def test_package_entrypoint_also_works(self):
        """`python -m forgemind.api`(__main__.py)同样要能用"""
        port = _free_port()
        proc = subprocess.Popen(
            [sys.executable, "-m", "forgemind.api",
             "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=_env(), cwd="/tmp",
        )
        try:
            d = _wait_health(proc, port)  # 不就绪时自行 pytest.fail
            assert isinstance(d, dict), f"python -m forgemind.api 未在 {port} 就绪"
            assert d["status"] == "ok"
        finally:
            _stop(proc)
