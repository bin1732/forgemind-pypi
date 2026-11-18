# Copyright (c) 2026 灵感引擎工坊 (bin1732) | SPDX-License-Identifier: Apache-2.0
"""接口的失败响应体不许漏内部。

响应体是给第三方调用方看的,不是给排查用的。里面出现异常类名、本机
路径或整条 SQL,调用方要么被误导(以为是服务端坏了),要么顺手把内部
结构带走了。

这些字段的措辞与清洗规则在 `forgemind.core.error_text`,命令行与 MCP
共用那一处 —— 这里盯的是**接口这条通道真的按那处办事**。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from forgemind.api.main import app
from forgemind.core.observability.logging import DataError


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _raise(monkeypatch, exc: BaseException) -> None:
    """让真的因子端点抛出指定异常。"""
    from forgemind.core import factors

    def boom(*args, **kwargs):
        raise exc

    monkeypatch.setattr(factors, "get_all_factors", boom)


class TestFailureBodyHasNoInternals:
    def test_our_own_error_keeps_the_human_text(self, client, monkeypatch):
        """我们自己的错误文本是有用的,得留着 —— 调用方据此改参数。"""
        _raise(monkeypatch, DataError("symbol 不能为空"))
        r = client.get("/api/v1/features")
        assert r.status_code == 422, r.text[:300]
        body = r.json()
        assert body["message"] == "symbol 不能为空", body
        assert body["error"] != "DataError", body
        assert body["code"], body

    def test_third_party_error_does_not_leak_its_class_name(self, monkeypatch):
        """第三方库的原始报错里有本机路径、内部表名与整条 SQL。

        这类异常不走我们自己的处理器,交给服务框架 ⇒ 客户端该看到的是
        一个干干净净的 500。`raise_server_exceptions=False` 让测试看到
        真实服务器会回什么,而不是把异常原样抛回来。
        """
        _raise(
            monkeypatch,
            OSError(
                "Could not set lock on file '/home/someone/data/main.duckdb': "
                "Conflicting lock is held in /usr/bin/python3.11 (PID 2921)"
            ),
        )
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/api/v1/features")
        assert r.status_code == 500, r.text[:300]
        text = r.text
        assert "OSError" not in text, text
        assert "/home/someone" not in text, text
        assert "PID 2921" not in text, text
        assert "main.duckdb" not in text, text

    def test_details_are_cleaned_not_dumped(self, client, monkeypatch):
        """诊断上下文里带内部痕迹的键整个丢掉,干净的值留着。"""
        _raise(
            monkeypatch,
            DataError(
                "取数失败",
                db_path="/home/someone/data/main.duckdb",
                symbol="600519",
                rows=42,
            ),
        )
        r = client.get("/api/v1/features")
        assert r.status_code == 422, r.text[:300]
        details = r.json()["details"]
        assert "db_path" not in details, details
        assert "/home/someone" not in r.text, r.text
        assert details.get("symbol") == "600519", details
        assert details.get("rows") == 42, details

    def test_sql_in_details_does_not_survive(self, client, monkeypatch):
        """SQL 片段也是内部结构。"""
        _raise(
            monkeypatch,
            DataError("查不到", query="SELECT * FROM main.kline_daily WHERE symbol='600519'"),
        )
        r = client.get("/api/v1/features")
        assert r.status_code == 422, r.text[:300]
        assert "SELECT" not in r.text, r.text
        assert "kline_daily" not in r.text, r.text
