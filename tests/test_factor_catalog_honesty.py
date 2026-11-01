# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""因子目录必须与实际产出**完全一致** —— 声明了却算不出来就是撒谎

`get_all_factors()` 是 MCP `get_feature` / API `/api/v1/features` 的公开目录。
它列出的每个名字都会出现在用户面前,并配上一段公式说明。用户按名去取,
拿到的却是"这个因子没有被计算"。

真实抓到的三处:
  - BOLL_POS / BOLL_PCT / BOLL_DISTANCE 被声明,但计算函数只产出
    BOLL_UPPER / MID / LOWER —— 三个名字永远是空承诺
  - BOLL_UPPER / MID / LOWER 反过来:算出来了却没进目录
  - technical_indicators 分步计算的 22 个暂存列(_rsi / _dif / _macd …)
    泄漏进了因子输出面

所以这里钉三件事:声明的都能算、算的都在声明里、输出面没有内部列。
"""

import pathlib

import numpy as np
import polars as pl


def _panel(ns=4, nd=300, seed=0):
    rng = np.random.default_rng(seed)
    sym = np.repeat([f"S{i:02d}" for i in range(ns)], nd)
    base = 10 ** rng.uniform(0.5, 3.0, ns)
    close = np.repeat(base, nd) * np.exp(np.cumsum(rng.normal(0, 0.02, ns * nd)))
    return pl.DataFrame({
        "symbol": sym, "date": np.tile(np.arange(nd), ns),
        "open": close * .999, "high": close * 1.01, "low": close * .98,
        "close": close, "volume": rng.integers(1e5, 1e6, ns * nd).astype(float),
    }).sort(["symbol", "date"])


RAW = {"symbol", "date", "open", "high", "low", "close", "volume"}
ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestDeclaredFactorsAreAllComputed:
    def test_alpha158_declaration_matches_output(self):
        from forgemind.core.factors.alpha158 import (
            compute_alpha158,
            list_alpha158_factors,
        )

        out = set(compute_alpha158(_panel().lazy()).collect().columns)
        declared = set(list_alpha158_factors())
        assert not declared - out, (
            f"声明了却算不出来: {sorted(declared - out)}")
        assert not (out - RAW - declared), (
            f"算出来了却没进目录: {sorted(out - RAW - declared)}")

    def test_no_internal_columns_leak_into_the_factor_surface(self):
        """分步计算的暂存列(以 _ 开头)不是因子,不能出现在输出里"""
        from forgemind.core.factors.alpha158 import compute_alpha158

        out = compute_alpha158(_panel().lazy()).collect().columns
        leaked = [c for c in out if c.startswith("_")]
        assert not leaked, f"内部暂存列泄漏到因子输出面: {leaked}"

    def test_boll_derived_factors_are_real(self):
        """BOLL_POS / PCT / DISTANCE 必须真的有值,不是列名占位"""
        from forgemind.core.factors.alpha158 import compute_alpha158

        out = compute_alpha158(_panel(nd=120).lazy()).collect()
        for f in ("BOLL_POS", "BOLL_PCT", "BOLL_DISTANCE",
                  "BOLL_UPPER", "BOLL_MID", "BOLL_LOWER"):
            assert f in out.columns, f"{f} 缺失"
            v = out[f].to_numpy()
            assert np.isfinite(v).sum() > 20, f"{f} 有效值太少"
            assert np.nanstd(v) > 0, f"{f} 恒为常数"

    def test_catalog_size_matches_reality(self):
        from forgemind.core.factors import get_all_factors
        from forgemind.core.factors.alpha101 import (
            list_alpha101_factors,
        )
        from forgemind.core.factors.alpha158 import (
            list_alpha158_factors,
        )

        a158 = set(list_alpha158_factors())
        a101 = set(list_alpha101_factors())
        assert len(a158 & a101) == 0, "两个家族的因子名不应重叠"
        catalog = set(get_all_factors())
        assert a158 <= catalog and a101 <= catalog, "两个家族都应在公开目录里"
        assert len(catalog) >= len(a158) + len(a101)


class TestCatalogIsServedToUsers:
    """目录会被 MCP / API 原样吐给用户,内容必须可用"""

    def test_every_catalog_entry_resolves_through_mcp(self):
        """目录里的每个名字都必须能被 get_feature 解析出来

        走 JSON-RPC 层(用户实际用的那条路),而不是直接调内部方法。
        """
        import json as _json
        import queue
        import subprocess
        import sys
        import threading
        import uuid as _uuid

        from forgemind.core.factors import get_all_factors

        proc = subprocess.Popen(
            [sys.executable, "-m", "forgemind.cli", "mcp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True)
        q = queue.Queue()

        def pump():
            for line in proc.stdout:
                line = line.strip()
                if line:
                    try:
                        q.put(_json.loads(line))
                    except _json.JSONDecodeError:
                        pass

        threading.Thread(target=pump, daemon=True).start()

        def send(o):
            proc.stdin.write(_json.dumps(o) + chr(10))
            proc.stdin.flush()

        def read():
            try:
                return q.get(timeout=60)
            except queue.Empty:
                return None

        bad = []
        try:
            send({"jsonrpc": "2.0", "id": "1", "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                             "clientInfo": {"name": "t", "version": "1"}}})
            read()
            for f in get_all_factors():
                send({"jsonrpc": "2.0", "id": str(_uuid.uuid4()),
                      "method": "tools/call",
                      "params": {"name": "get_feature", "arguments": {"name": f}}})
                m = read()
                if not m or "result" not in m:
                    bad.append((f, "无响应")); continue
                body = _json.loads(m["result"]["content"][0]["text"])
                if "error" in body:
                    bad.append((f, str(body["error"])[:50]))
        finally:
            try:
                proc.stdin.close(); proc.terminate(); proc.wait(timeout=10)
            except Exception:
                proc.kill()
        assert not bad, f"目录里有因子取不到定义({len(bad)} 个): {bad[:5]}"


class TestReadmeNumbersAreCurrent:
    """README 里的数字必须和代码一致 —— 声明错了就等于骗用户

    实际抓到过两处:README 写 "166 Alpha Factors" 而代码是 166 但分布
    标成 "Alpha158 (149) · Alpha101 (17)",而 alpha101 实际只有 11 个。
    """

    def test_factor_total_in_readme_matches_code(self):
        import re

        from forgemind.core.factors import get_all_factors

        real = len(get_all_factors())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        m = re.search(r"(\d+)\s+Alpha Factors", readme)
        assert m, "README 里找不到 Alpha Factors 的数量声明"
        assert int(m.group(1)) == real, (
            f"README 说 {m.group(1)} 个因子,代码里是 {real} 个")

    def test_family_breakdown_in_readme_matches_code(self):
        import re

        from forgemind.core.factors.alpha101 import list_alpha101_factors
        from forgemind.core.factors.alpha158 import list_alpha158_factors

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        m = re.search(r"Alpha158 \((\d+)\).*?Alpha101 \((\d+)\)", readme)
        assert m, "README 里找不到家族分布"
        assert int(m.group(1)) == len(list_alpha158_factors()), (
            f"README 说 Alpha158 {m.group(1)},实际 {len(list_alpha158_factors())}")
        assert int(m.group(2)) == len(list_alpha101_factors()), (
            f"README 说 Alpha101 {m.group(2)},实际 {len(list_alpha101_factors())}")

