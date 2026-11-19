# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""接口输出判据:它自己也得可靠。

它盯的是"每个端点带合法参数真打一遍,响应里没有内部实现,库被占着时
说的是'读不到'而不是'没有数据'"。这类判据最容易出两种错:

- 规则太宽 ⇒ 一堆假红 ⇒ 没人看它。
- 规则太窄 ⇒ 真的漏了也放过。

所以这里逐条钉:该报的报、不该报的不报,而且用**编出来的输出**做样本 ——
真跑一遍能验"整条链路合规",却验不出**哪条规则**在起作用。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_api_output_clean as api_clean  # noqa: E402


class TestProbeTable:
    def test_every_api_route_is_probed(self):
        """API 里注册的每个路由都要在探针表里。

        少一个,判据就漏了那个端点 —— 它出问题时没人会发现。新加端点
        忘了配探针,这一条当场报出来。
        """
        from fastapi.routing import APIRoute

        from forgemind.api.main import app

        routes = {
            r.path
            for r in app.routes
            if isinstance(r, APIRoute) and r.path not in ("/openapi.json",)
        }
        probed = {path for _, path, _, _ in api_clean.API_PROBES}
        missing = {p for p in routes if p not in probed}
        # /api/v1/agent/{thread_id}/approve 与 /reject 的探针里写的是
        # 具体 id,这里按前缀对上。
        missing = {
            p
            for p in missing
            if not any(
                pr.startswith(p.split("{")[0]) or p.startswith(pr.split("{")[0]) for pr in probed
            )
        }
        assert not missing, f"这些端点没进探针表: {sorted(missing)}"

    def test_read_db_paths_exist_in_probes(self):
        """库被占着时要挨个核的端点,也得在探针表里。"""
        probed = {path for _, path, _, _ in api_clean.API_PROBES}
        for path in api_clean.READ_DB_PATHS:
            assert path in probed, f"{path} 在只读名单里,却没进探针表"


class _Resp:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def json(self):
        import json as _json

        return _json.loads(self.text)


class TestRules:
    def test_a_dirty_response_is_caught(self):
        """含异常类名与 SQL 的响应必须被扫出来。"""
        resp = _Resp(500, '{"detail": "CatalogException: IO Error: SELECT * FROM main.kline"}')
        hits = [k for k, _ in api_clean.leak._scan(resp.text, api_clean.leak.COMPILED_LEAKS)]
        assert hits, "含内部实现的响应没被扫出来"

    def test_a_clean_response_passes(self):
        resp = _Resp(200, '{"status": "ok", "cash": 1000.0, "message": null}')
        assert not api_clean.leak._scan(resp.text, api_clean.leak.COMPILED_LEAKS)

    def test_missing_and_unreadable_are_distinguished(self):
        """ "没有数据"与"读不到"是两回事,判据要能分开。"""
        assert any(m in "库里没有该标的的行情" for m in api_clean.MISSING_MARKERS)
        assert not any(m in "库里没有该标的的行情" for m in api_clean.UNREADABLE_MARKERS)
        assert any(m in "本地库被另一个进程占着,暂时用不了" for m in api_clean.UNREADABLE_MARKERS)

    def test_the_checker_passes_its_own_synthetic_samples(self):
        """判据自带的双向验必须自己也过 —— 它自己坏了要说出来。"""
        problems = api_clean.check_rules_against_synthetic_samples()
        assert problems == [], problems

    def test_error_response_without_explanation_is_caught(self):
        """错误响应只有状态码没有说明 ⇒ 判据要报。"""
        assert not api_clean._has_explanation(_Resp(400, "{}"))
        assert api_clean._has_explanation(_Resp(400, '{"detail": "参数不对"}'))
