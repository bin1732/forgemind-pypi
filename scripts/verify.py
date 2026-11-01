# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3

"""ForgeMind 全量验证 —— 一条命令跑完

    python scripts/verify.py                # 全部
    python scripts/verify.py --quick        # 跳过需要装依赖的环节
    python scripts/verify.py --only lint tests
    python scripts/verify.py --list

设计原则(都来自真实踩过的坑):
  * 内存受限机器上 pytest 必须分批,否则 torch 相关测试会 OOM 段错误,
    且段错误会让 pytest 把后续用例全记为 FAILED,污染结论。
  * 任一环节失败不中断后续环节 —— 一次跑完要把所有问题都暴露出来。
  * 结论只有两种:全绿或红,不做"部分通过"这种含糊表述。
  * 每个环节的原始输出落到 .verify/ 下,便于事后查证,而不是只留一行绿字。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 默认写到本地盘:源码树在 NAS 挂载上,日志文件会间歇性不可见,
# 曾导致验证脚本自身抛 FileNotFoundError。FORGEMIND_VERIFY_OUT 可覆盖。
OUT = Path(os.environ.get("FORGEMIND_VERIFY_OUT", "/tmp/forgemind-verify-out"))
# venv 必须放在本地盘:源码树位于 NAS 挂载上,在那里建 venv 只会生成
# lib/ 而没有 bin/,导致后续所有步骤报 "No such file: bin/pip"。
VENV = Path(
    os.environ.get("FORGEMIND_VERIFY_VENV", tempfile.gettempdir() + "/forgemind-verify-venv")
)

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = RESET = ""

# 引入 torch 的测试文件必须单独跑:3GB 机器上单进程累积会 OOM。
TORCH_HEAVY_TESTS = ["test_deep_code_audit.py", "test_multimodal_storage.py"]


@dataclass
class Step:
    name: str
    ok: bool | None = None
    detail: str = ""
    seconds: float = 0.0
    skipped: bool = False
    notes: list[str] = field(default_factory=list)


STEPS: list[Step] = []


def run(cmd, cwd=None, timeout=3600, env=None, to_file: str | None = None) -> tuple[int, str]:
    """执行命令。

    to_file 不为空时把输出直接落盘而不是 capture_output:
    pytest 的输出动辄几百 KB,再叠加它自身的内存占用,在 3GB 机器上
    capture_output 容易被 OOM killer 干掉(返回 -9 且没有失败摘要)。
    """
    e = dict(os.environ)
    e.update(env or {})
    if to_file:
        OUT.mkdir(exist_ok=True)
        path = OUT / to_file
        with open(path, "w", encoding="utf-8", errors="replace") as fh:
            try:
                p = subprocess.run(
                    cmd,
                    cwd=cwd or ROOT,
                    stdout=fh,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    env=e,
                )
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = 124
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        return rc, text
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True, timeout=timeout, env=e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def log(msg=""):
    print(msg, flush=True)


def step(name: str, fn, *, quick_skip: bool = False, quick: bool = False) -> Step:
    s = Step(name=name)
    if quick and quick_skip:
        s.skipped, s.ok = True, None
        STEPS.append(s)
        log(f"  {YELLOW}⏭{RESET}  {name}  {DIM}(--quick 跳过){RESET}")
        return s
    log(f"  {DIM}→{RESET} {name} ...")
    t0 = time.time()
    try:
        s.ok, s.detail = fn()
    except Exception as exc:  # 单步异常不应中断整体
        s.ok, s.detail = False, f"{type(exc).__name__}: {exc}"
    s.seconds = time.time() - t0
    STEPS.append(s)
    icon = f"{GREEN}✓{RESET}" if s.ok else f"{RED}✗{RESET}"
    log(f"  {icon} {name}  {DIM}({s.seconds:.1f}s){RESET}")
    if not s.ok and s.detail:
        for ln in [x for x in s.detail.splitlines() if x.strip()][-6:]:
            log(f"      {RED}{ln.strip()[:150]}{RESET}")
    return s


# ---------- 各环节 ----------


def s_lint() -> tuple[bool, str]:
    """对发布出去的代码做 lint 门禁。

    口径与流水线一致(同样的忽略项与行宽),门禁的范围是随包发布的
    代码:forgemind/ 与 scripts/。

    测试目录里有大量刻意的写法(比如 test_TokenError 这样的函数名),
    把整个仓库的 finding 都算成失败,门禁就永远红 —— 永远红的门禁
    等于没有门禁,久了就没人当回事。测试目录的 finding 仍然统计出来
    一并报出,不藏。
    """
    ruff = find_tool("ruff")
    if not ruff:
        return False, "ruff 不可用(未安装)"
    args = ["--ignore=F401,F841", "--line-length", "120"]
    rc, out = run([ruff, "check", "forgemind/", "scripts/", *args])
    if rc == 0:
        rc2, out2 = run([ruff, "check", "forgemind/", "scripts/", *args, "--statistics"])
        detail = out2 or "All checks passed"
        rc3, out3 = run([ruff, "check", "tests/", *args, "--output-format=concise"])
        extra = [ln for ln in out3.splitlines() if ln and not ln.startswith(("Found", "["))]
        if extra:
            detail += f" | 测试目录另有 {len(extra)} 处风格提示,不作门禁"
        return True, detail
    save("lint.txt", out)
    return False, out


def _pytest_batch(
    files: list[str], tag: str = "b", marker: str = "not slow and not heavy"
) -> tuple[bool, str]:
    if not files:
        return True, "(无文件)"
    py = python_with("pytest")
    rc, out = run(
        [py, "-m", "pytest", *files, "-q", "-p", "no:cacheprovider", "-m", marker, "--tb=line"],
        timeout=2400,
        to_file=f"pytest_{tag}.log",
    )
    # pytest 打印完汇总并不代表进程正常退出:若此时被 OOM killer 干掉
    # (返回 -9)或卡在非 daemon 线程上直到超时(124),日志看起来是"全过"
    # 但退出码非 0。因此必须看退出码,不能只看日志。
    if rc == 0:
        return True, out
    reason = {
        124: "批次超时(2400s):pytest 已打印汇总但进程未退出,通常是残留非 daemon 线程",
        -9: "被 SIGKILL 终止(内存不足 / OOM killer)",
    }.get(rc, "")
    if rc < 0:
        reason = reason or f"被信号 {-rc} 终止"
    return False, (
        f"退出码 {rc} {reason}\n日志末尾: " + "\n".join(out.strip().splitlines()[-3:])[:400]
    )


def _heavy_concurrency_files() -> set[str]:
    """按 heavy 规则筛出并发重测试文件。

    规则只定义在 tests/conftest.py 一处,这里直接复用,不在验证脚本里
    复制第二份判定逻辑——两处各写一套必然漂移。
    """
    import importlib.util

    conftest_path = ROOT / "tests" / "conftest.py"
    try:
        spec = importlib.util.spec_from_file_location("_fg_conftest", conftest_path)
        if spec is None or spec.loader is None:
            return set()
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        patterns = list(mod._LONG_RUNNING_PATTERNS)
    except Exception:
        return set()
    if not patterns:
        return set()
    files = set()
    for p in (ROOT / "tests").glob("test_*.py"):
        nodeid = f"tests/{p.name}"
        if any(pat.search(nodeid) for pat in patterns):
            files.add(nodeid)
    return files


def s_tests() -> tuple[bool, str]:
    """分批跑:重测试单独一批,避免 OOM 段错误污染结果"""
    allf = sorted(p.name for p in (ROOT / "tests").glob("test_*.py"))
    concurrency_heavy = _heavy_concurrency_files()
    torch_heavy = [f"tests/{f}" for f in allf if f in TORCH_HEAVY_TESTS]
    heavy_paths = {f"tests/{f}" for f in allf if f"tests/{f}" in concurrency_heavy}
    light = [
        f"tests/{f}" for f in allf if f not in TORCH_HEAVY_TESTS and f"tests/{f}" not in heavy_paths
    ]
    # 轻量组再对半,进一步压低峰值内存
    # 批次越小峰值内存越低;3GB 机器上 16 个文件一批会被 OOM killer 干掉
    chunk = int(os.environ.get("FORGEMIND_VERIFY_CHUNK", "8"))
    light_batches = [light[i : i + chunk] for i in range(0, len(light), chunk)]
    # 每批带自己的 marker 筛选表达式:
    #   常规批  -> 排除 slow 与 heavy
    #   torch 批 -> torch 文件没有 heavy 标记,只排除 slow
    #   并发批  -> 只跑 heavy 标记的用例
    batches: list[tuple[list[str], str]] = [
        (b, "not slow and not heavy") for b in light_batches if b
    ]
    if torch_heavy:
        batches.append((torch_heavy, "not slow"))
    if heavy_paths:
        batches.append((sorted(heavy_paths), "heavy"))

    total_ok, tail = True, []
    for i, (b, marker) in enumerate(batches, 1):
        # _pytest_batch 返回 (ok: bool, detail: str),退出码由它内部判断。
        # 退出码必须参与判定:Python 里 False == 0,若把布尔值当退出码用,
        # 失败批次会被静默放行。
        ok, detail = _pytest_batch(b, tag=f"b{i}", marker=marker)
        name = f"batch {i}/{len(batches)} ({len(b)} 文件)"
        log(f"      {DIM}{name}{RESET}")
        if not ok:
            total_ok = False
            save(f"tests_batch{i}.txt", detail)
            key = [
                ln
                for ln in detail.splitlines()
                if ln.startswith("FAILED") or " error" in ln or "Error" in ln
            ]
            key = key[:12] or [ln for ln in detail.splitlines() if ln.strip()][-6:]
            tail.append(
                f"[{name}] 失败: {detail.splitlines()[0] if detail.strip() else '(无信息)'}\n"
                + "\n".join(key)[:1800]
            )
    return total_ok, "\n".join(tail)


def s_build() -> tuple[bool, str]:
    OUT.mkdir(exist_ok=True)
    if VENV.exists():
        shutil.rmtree(VENV)
    rc, out = run([sys.executable, "-m", "venv", str(VENV)])
    if rc != 0:
        return False, "创建 venv 失败: " + out
    pip = VENV / "bin" / "pip"
    idx = pip_index()
    env = {"PIP_INDEX_URL": idx} if idx else {}
    if not idx:
        return False, ("所有候选 pip 索引都不可达;请设 FORGEMIND_PIP_INDEX 指向可用镜像")
    # --no-isolation 构建要求当前环境先满足 [build-system] requires。
    # 新建 venv 自带的 setuptools 通常过低,且项目可能声明了额外后端依赖
    # (例如 setuptools-pkg),漏装会导致 egg_info 阶段报 Unmet dependencies。
    requires = build_requires()
    reqs = ["pip", "wheel", "build", *requires]
    rc, out = run([str(pip), "install", "-q", "--upgrade", *reqs], env=env, timeout=1800)
    if rc != 0:
        return False, f"装构建依赖失败(索引 {idx}): " + out[-1500:]
    chk = run(
        [
            str(VENV / "bin" / "python"),
            "-c",
            "import setuptools, wheel; print(setuptools.__version__)",
        ],
        timeout=120,
    )
    if chk[0] != 0:
        return False, f"构建依赖自检失败: {chk[1][-500:]}"
    ver = chk[1].strip().splitlines()[-1] if chk[1].strip() else "?"
    return True, f"venv 就绪,setuptools {ver},索引 {idx}"
    return True, f"venv 就绪 @ {idx}"


def s_wheel() -> tuple[bool, str]:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.whl"):
        old.unlink()
    py = venv_python()
    rc, out = run(
        [py, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(OUT), "."], timeout=1800
    )
    if rc != 0:
        return False, out
    whls = list(OUT.glob("*.whl"))
    if not whls:
        return False, "未产出 wheel"
    return True, f"{whls[0].name} ({whls[0].stat().st_size // 1024} KB)"


def s_install() -> tuple[bool, str]:
    whls = list(OUT.glob("*.whl"))
    if not whls:
        return False, "没有可安装的 wheel(先跑 build)"
    pip = VENV / "bin" / "pip"
    idx = pip_index()
    env = {"PIP_INDEX_URL": idx} if idx else {}
    # 先把 wheel 复制到本地盘再装:.verify 位于 NAS 挂载上,
    # 长达数分钟的安装过程中该文件可能不可见(FileNotFoundError),
    # 本地盘则稳定得多。
    local = VENV / whls[0].name
    shutil.copy2(whls[0], local)
    rc, out = run([str(pip), "install", str(local), "-q", "--no-input"], timeout=3600, env=env)
    if rc != 0:
        save("install.txt", out)
    return rc == 0, (out or "")[-2500:]


def s_smoke() -> tuple[bool, str]:
    """按真实用户路径走一遍:全部子命令 + 策略 + MCP + API"""
    script = r'''
import asyncio, json, os, sys, tempfile, subprocess
os.chdir(tempfile.mkdtemp())
fails = []

def check(name, fn):
    try:
        fn(); print(f"PASS {name}")
    except Exception as e:
        fails.append(f"{name}: {type(e).__name__}: {e}"); print(f"FAIL {name}: {e}")

from forgemind.cli import main as cli_main

def _cli(*args):
    sys.argv = ["forgemind", *args]
    try: cli_main()
    except SystemExit: pass
    except Exception as e: raise AssertionError(f"{args}: {e}")

check("cli:info",        lambda: _cli("info"))
check("cli:signal",      lambda: _cli("signal"))
check("cli:router-demo", lambda: _cli("router-demo"))

def _bt():
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _cli("backtest", "--start", "2024-01-01", "--end", "2024-12-31")
    assert "Total Return" in buf.getvalue(), buf.getvalue()[:200]
check("cli:backtest", _bt)

# 策略名拼错过一次(RSIRevision),所以这里从真实注册表取名而不是硬编码,
# 避免验证脚本自己写错名字却报成产品缺陷。
from forgemind.core.strategies.library import STRATEGY_REGISTRY
from forgemind.core.strategies.extended_library import list_strategies as _lst
_STRATS = list(STRATEGY_REGISTRY) + list(_lst())
# 这三个必须靠外部模型/双标的,CLI 无法直接跑,单独在下面断言它们会给出明确指引
_NEED_PARAMS = {"PairsTrading", "LightGBMStrategy", "OnlineLearningStrategy"}
for s in _STRATS:
    if s in _NEED_PARAMS:
        continue
    def _mk(s=s):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _cli("backtest", "--strategy", s, "--start", "2024-01-01", "--end", "2024-12-31")
        assert "Total Return" in buf.getvalue(), buf.getvalue()[:200]
    check(f"strategy:{s}", _mk)

def _mcp():
    """MCP 协议全量走一遍:工具、资源、提示词都要真的响应。

    原来只调了 5 个工具,而且只断言"没报错"。返回了 JSON 不等于干了活
    —— 没被调过的工具永远不会被发现有问题。这里每个工具都带合法参数
    真调一遍,资源逐个读,提示词按声明的参数渲染。
    """
    from forgemind.mcp.server import ForgeMindMCPServer

    tool_calls = [
        ("search_features", {"query": "momentum"}),
        ("get_feature", {"name": "kmid"}),
        ("trace_feature_usage", {"feature_id": "KMID"}),
        ("run_backtest", {"strategy": "ma_cross", "symbol": "600519",
                          "start": "2024-01-01", "end": "2024-06-30"}),
        ("output_signal", {"symbol": "600519.SH", "side": "buy",
                           "confidence": 0.8, "rationale": "verify"}),
        ("check_ic_decay", {"feature_name": "kmid", "window_days": 30}),
        ("list_factor_ic", {"symbol": "600519", "window_days": 5}),
        ("get_kline", {"symbol": "600519", "limit": 5}),
        ("query_portfolio", {}),
        ("stock_pick", {"universe": ["600519", "000001"], "top_n": 2}),
    ]
    resource_uris = [
        "forgemind://features", "forgemind://strategies", "forgemind://symbols",
        "forgemind://signals", "forgemind://brokers", "forgemind://portfolio",
    ]
    # 编造数据防线:这些词在源码里 0 出现,只可能来自编造的内容
    fabrications = ("mock data", "placeholder", "dummy", "fake_", "示例数据")

    async def m():
        srv = ForgeMindMCPServer()

        listed = await srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        names = {t["name"] for t in listed["result"]["tools"]}
        assert names == {n for n, _ in tool_calls}, (
            f"工具清单与验证覆盖不一致: {sorted(names)}")

        for n, a in tool_calls:
            r = await srv.handle_request({"jsonrpc": "2.0", "id": 2,
                                          "method": "tools/call",
                                          "params": {"name": n, "arguments": a}})
            assert "error" not in r, f"{n}: {r.get('error')}"
            t = r["result"]["content"][0]["text"]
            assert t.strip(), f"{n} 返回空内容"
            for bad in fabrications:
                assert bad.lower() not in t.lower(), f"{n} 返回里有编造标记 {bad}"
            d = json.loads(t)
            if n == "query_portfolio":
                assert d.get("status") in ("ok", "empty"), d
                # 持仓数量与市值只可能来自编造
                assert "80000" not in t and "200000" not in t
            if n == "run_backtest":
                # 数据来源必须如实标注,不能把合成行情说成真数据
                assert d.get("is_real_data") in (True, False), d
                assert d.get("data_source"), d
                if not d.get("is_real_data"):
                    assert d.get("warning"), "降级到合成行情却没有声明"

        for uri in resource_uris:
            r = await srv.handle_request({"jsonrpc": "2.0", "id": 3,
                                          "method": "resources/read",
                                          "params": {"uri": uri}})
            assert "error" not in r, f"{uri}: {r.get('error')}"
            contents = r["result"]["contents"]
            assert contents, f"{uri} 没有内容"
            json.loads(contents[0]["text"])

        # 提示词:list 要声明参数,get 要把参数渲染进正文
        plist = await srv.handle_request({"jsonrpc": "2.0", "id": 4,
                                           "method": "prompts/list", "params": {}})
        for p in plist["result"]["prompts"]:
            args = {a["name"]: "600519" for a in p.get("arguments", [])}
            r = await srv.handle_request({"jsonrpc": "2.0", "id": 5,
                                          "method": "prompts/get",
                                          "params": {"name": p["name"],
                                                     "arguments": args}})
            assert "error" not in r, f"{p['name']}: {r.get('error')}"
            text = " ".join(msg.get("content", {}).get("text", "")
                            for msg in r["result"]["messages"])
            leftovers = re.findall(r"\{\w+\}", text)
            assert not leftovers, (
                f"{p['name']} 的提示词里残留未替换的占位符 {leftovers}")
    asyncio.run(m())
check("mcp:tools", _mcp)

def _api():
    from fastapi.testclient import TestClient
    from forgemind.api.main import app
    with TestClient(app) as c:
        for ep in ["/health","/api/v1/info","/api/v1/health/services","/mcp/tools/list"]:
            assert c.get(ep).status_code == 200, ep
        r = c.get("/api/v1/health/services").text
        for leak in ["127.0","::1","password","Traceback","site-packages"]:
            assert leak not in r, f"泄露 {leak}"
        for body in [{"start_date":"bad","end_date":"2024-06-01"},
                     {"start_date":"2024-06-01","end_date":"2024-01-01"},
                     {"start_date":"2024-01-01","end_date":"2024-06-01",
                      "fast_period":50,"slow_period":10}]:
            assert c.post("/api/v1/backtest/run", json=body).status_code == 422, body
check("api:endpoints", _api)

def _metrics():
    import numpy as np, pandas as pd
    from empyrical import sharpe_ratio, max_drawdown, sortino_ratio
    from forgemind.core.backtest.engine import SimpleBacktestEngine
    from forgemind.core.strategies.base import MovingAverageCrossStrategy
    rng = np.random.default_rng(11); n = 500
    close = 100*np.exp(np.cumsum(rng.normal(0.0004, 0.018, n)))
    df = pd.DataFrame({"open":close*(1+rng.normal(0,0.003,n)),"high":close*1.01,
                       "low":close*0.99,"close":close,
                       "volume":rng.integers(1_000_000,5_000_000,n)})
    s = MovingAverageCrossStrategy(parameters={"fast_period":10,"slow_period":40})
    e = SimpleBacktestEngine(initial_capital=100_000.0)
    res = e.run(s, df)
    r = e._simulate_equity(df, s.generate_signals(df)).pct_change().dropna()
    for got, ref, label in [(res.sharpe, sharpe_ratio(r.values), "sharpe"),
                            (res.max_drawdown, max_drawdown(r.values), "maxdd"),
                            (res.sortino, sortino_ratio(r.values), "sortino")]:
        assert abs(float(got)-float(ref)) < 1e-8, f"{label} {got} != {ref}"
check("metrics:vs-empyrical", _metrics)

def _equity():
    """资金曲线不得重复计入持仓期涨幅"""
    import numpy as np, pandas as pd
    from forgemind.core.backtest.engine import SimpleBacktestEngine
    idx = pd.date_range("2024-01-01", periods=4)
    o = np.array([99.,100.,130.,130.]); c = o.copy()
    df = pd.DataFrame({"open":o,"high":c*1.01,"low":c*0.99,"close":c,"volume":1e6}, index=idx)
    sg = pd.DataFrame({"entries":[True,False,False,False],
                       "exits":[False,True,False,False]}, index=idx)
    e = SimpleBacktestEngine(initial_capital=100_000., fees=0., slippage_bps=0., use_next_open=True)
    eq = e._simulate_equity(df, sg)
    assert abs(eq.iloc[2]-130_000.) < 1e-6, f"同日止盈应为 130000,实得 {eq.iloc[2]}"
check("equity:no-double-count", _equity)

def _pick():
    from forgemind.core.agents.stock_picker import StockPickerAgent
    raws = [{"momentum": v} for v in (-0.3,-0.15,-0.05,0.,0.03,0.08,0.15,0.3)]
    out = StockPickerAgent._cross_sectional_normalize(raws)
    vals = [o["momentum"] for o in out]
    assert vals == sorted(vals) and len(set(vals)) == len(vals), vals
check("picker:discriminating", _pick)

print("__RESULT__", json.dumps(fails, ensure_ascii=False))
'''
    py = venv_python()
    rc, out = run([py, "-c", script], timeout=2400, to_file="smoke.log")
    for ln in out.splitlines():
        if ln.startswith(("PASS ", "FAIL ")):
            icon = f"{GREEN}✓{RESET}" if ln.startswith("PASS") else f"{RED}✗{RESET}"
            log(f"      {icon} {ln[5:]}")
    if "__RESULT__" not in out:
        return False, out[-3000:]
    fails = json.loads(out.split("__RESULT__")[1].splitlines()[0])
    return not fails, "\n".join(fails)


def s_repo_consistency() -> tuple[bool, str]:
    """私人仓与公开仓的源码必须一致(公开仓不含源码时跳过)"""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return True, "无 GITHUB_TOKEN,跳过"
    try:
        import urllib.request

        def tree(repo):
            req = urllib.request.Request(
                f"https://api.github.com/repos/bin1732/{repo}/git/trees/main?recursive=1",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
            return {x["path"]: x["sha"] for x in data.get("tree", []) if x["type"] == "blob"}

        priv, pub = tree("forgemind"), tree("forgemind-pypi")
        skip = ("artifacts/", "pypi/", "releases/")
        common = [p for p in priv if p in pub and not p.startswith(skip)]
        # .gitignore / README 等托管仓自有文件本就允许不同
        allow = {".gitignore", "NOTICE", "README.md", "CHANGELOG.md", ".env.example"}
        diff = [p for p in sorted(common) if priv[p] != pub[p] and p not in allow]
        return not diff, (
            f"两仓共有 {len(common)} 文件,源码不一致 {len(diff)}: {diff}"
            if diff
            else f"两仓共有 {len(common)} 文件,源码一致"
        )
    except Exception as exc:
        return True, f"跳过: {exc}"


def build_requires() -> list[str]:
    """读取 pyproject.toml 的 [build-system].requires

    --no-isolation 构建时必须先把这些装进当前环境,否则 setuptools 会在
    egg_info 阶段报 "Unmet dependencies"(例如项目声明了 setuptools-pkg)。
    """
    import tomllib  # Python 3.11+ 内置(项目声明 requires-python>=3.11)

    pp = ROOT / "pyproject.toml"
    if not pp.exists():
        return ["setuptools>=68", "wheel"]
    try:
        data = tomllib.loads(pp.read_text(encoding="utf-8"))
    except Exception:
        return ["setuptools>=68", "wheel"]
    return list(data.get("build-system", {}).get("requires", ["setuptools>=68", "wheel"]))


# ---------- pip 索引探测 ----------

_FALLBACK_INDEXES = [
    "https://pypi.tuna.tsinghua.edu.cn/simple/",
    "https://mirrors.aliyun.com/pypi/simple/",
    "https://pypi.org/simple/",
]


def _index_reachable(url: str, timeout: int = 8) -> bool:
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "forgemind-verify"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def pip_index() -> str | None:
    """挑一个真正连得上的索引

    本项目的沙箱里 PIP_INDEX_URL 环境变量指向的镜像是不可达的
    (curl 返回 000),而 pip.conf 里的另一个是好的。pip 优先读环境变量,
    于是新建的 venv 会直接卡在 "Retrying ... connect=None"。
    这里主动探测,拿不到能用的索引就返回 None(让 pip 用它自己的默认)。
    """
    override = os.environ.get("FORGEMIND_PIP_INDEX")
    candidates = [override] if override else []
    candidates += [os.environ.get("PIP_INDEX_URL", "")] + _FALLBACK_INDEXES
    for url in candidates:
        if url and _index_reachable(url.rstrip("/") + "/fastapi/"):
            return url
    return None


# ---------- 工具 ----------


def venv_python() -> str:
    for name in ("python", "python3"):
        p = VENV / "bin" / name
        if p.exists():
            return str(p)
    return sys.executable


def python_with(module: str) -> str:
    """返回一个**确实能 import 指定模块**的解释器

    venv_python() 只看路径是否存在,而 verify-venv 是 s_build 之后才建、
    里面只装了 build 不装 pytest —— 测试批次若误用它会报
    "No module named pytest"。这里按能力挑,不按路径。
    """
    import importlib.util

    if importlib.util.find_spec(module):
        return sys.executable
    for name in ("python", "python3"):
        p = VENV / "bin" / name
        if p.exists():
            r = run([str(p), "-c", f"import {module}"], timeout=60)
            if r[0] == 0:
                return str(p)
    return sys.executable


def find_tool(name: str) -> str | None:
    for d in (VENV / "bin", ROOT / ".venv" / "bin", Path(sys.executable).parent):
        p = d / name
        if p.exists():
            return str(p)
    return shutil.which(name)


def save(name: str, text: str):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(text, encoding="utf-8")


# ---------- 主流程 ----------

ALL_STEPS = {
    "lint": s_lint,
    "tests": s_tests,
    "build": s_build,
    "wheel": s_wheel,
    "install": s_install,
    "smoke": s_smoke,
    "repo": s_repo_consistency,
}
NEEDS_VENV = {"install", "smoke"}


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeMind 全量验证")
    ap.add_argument("--quick", action="store_true", help="跳过需要装依赖的环节")
    ap.add_argument("--only", nargs="*", help="只跑指定环节")
    ap.add_argument("--list", action="store_true", help="列出所有环节")
    a = ap.parse_args()

    if a.list:
        for k, v in ALL_STEPS.items():
            print(f"  {k:10} {v.__doc__ or v.__name__}")
        return 0

    names = a.only or list(ALL_STEPS)
    unknown = [n for n in names if n not in ALL_STEPS]
    if unknown:
        print(f"未知环节: {unknown}  可用: {list(ALL_STEPS)}")
        return 2

    log(f"{DIM}ForgeMind 全量验证  root={ROOT}{RESET}\n")
    t0 = time.time()
    for n in names:
        step(n, ALL_STEPS[n], quick_skip=("install", "smoke"), quick=a.quick)
        if n == "build" and a.only and any(x in NEEDS_VENV for x in names):
            continue

    # ---- 汇总 ----
    ran = [s for s in STEPS if s.ok is not None]
    ok = [s for s in ran if s.ok]
    bad = [s for s in ran if not s.ok]
    skipped = [s for s in STEPS if s.skipped]

    log("\n" + "─" * 68)
    for s in STEPS:
        icon = (
            (f"{GREEN}✓{RESET}" if s.ok else f"{RED}✗{RESET}")
            if s.ok is not None
            else f"{YELLOW}⏭{RESET}"
        )
        log(f"  {icon} {s.name:<10} {DIM}{s.seconds:6.1f}s  {(s.detail or '')[:60]}{RESET}")
    log("─" * 68)
    log(
        f"  {len(ok)}/{len(ran)} 环节通过"
        + (f",{len(skipped)} 跳过" if skipped else "")
        + f"  耗时 {time.time() - t0:.1f}s"
    )
    if bad:
        log(f"\n  {RED}失败环节:{RESET} {', '.join(s.name for s in bad)}")
        log(f"  {DIM}原始输出见 .verify/ 目录{RESET}")
    log("")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
