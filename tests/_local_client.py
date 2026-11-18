# Copyright (c) 2026 灵感引擎工坊 (bin1732) | SPDX-License-Identifier: Apache-2.0
"""从进程内调本机专用端点时要带的头。

`/mcp` 与 `/api/pipeline` 免 API Key 校验(桌面端 sidecar 不带 key),
但它们能写库、能跑决策 —— 所以另设一道:必须带桌面端那个自定义头。
浏览器里的网页发这个头会触发 CORS 预检,预检被允许来源列表挡下 ⇒
网页驱动不了用户本机的库。

测试从进程内调这些端点,同样要带上这个头。头在哪定义只有一处
(`forgemind.api.main`),这里只负责判断"这个路径要不要带"。
"""

from __future__ import annotations

#: 本机专用端点的路径前缀。
LOCAL_ONLY_PREFIXES = ("/mcp", "/api/pipeline")


def local_headers(path: str) -> dict[str, str]:
    """这个路径要带的头。本机专用端点要,其余不要。"""
    from forgemind.api.main import MCP_CLIENT_HEADER, MCP_CLIENT_VALUE

    if any(path.startswith(p) for p in LOCAL_ONLY_PREFIXES):
        return {MCP_CLIENT_HEADER: MCP_CLIENT_VALUE}
    return {}
