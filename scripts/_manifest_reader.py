#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""读公开仓的发布清单 —— 一处实现,各处共用。

**为什么读要重试**:清单是发布刚写进去的,读它的那一瞬间接口可能给一个
空响应,或者 CDN 还没同步。拿到空的就当"线上没发布"是误判 —— 实测一次
就让整档桌面端验证红了,而发布本身是好的。

**"还不存在"与"读不到"要分开**:清单还不存在是第一次发布时的正常状态
(404);接口抖动、限流、返回一段文字是故障。混在一起的后果实测过:发布
时读"上一次版本号"失败被当成"没有上一次发布",版本号从头算起,发出
一个比线上还旧的号 —— 用户的 pip 根本不会升级。

用法:
    from _manifest_reader import read_manifest
    manifest = read_manifest("bin1732/forgemind-pypi", token)
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

#: 公开仓的清单在哪儿。
PUBLIC_REPO = "bin1732/forgemind-pypi"
MANIFEST_PATH = "releases/builds/manifest.json"


def read_manifest(
    repo: str,
    token: str,
    *,
    allow_missing: bool = False,
    attempts: int = 6,
    timeout: float = 60.0,
) -> dict | None:
    """读清单。返回解析后的字典。

    读不到就重试(递增退避);重试多次仍读不到就报错。

    allow_missing 为真时,"清单还不存在"(404)返回 None —— 那是第一次
    发布时的正常状态。其它读不到的情况仍然报错:把故障说成"没有"会
    让调用方得出错的结论。
    """
    url = f"https://api.github.com/repos/{repo}/contents/{MANIFEST_PATH}"
    last_error = "没试过"
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.raw",
                "User-Agent": "forgemind-manifest-reader",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            if not raw.strip():
                last_error = "响应是空的"
            else:
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    last_error = f"响应不是能解析的 JSON({exc})"
                else:
                    if not isinstance(payload, dict):
                        last_error = "响应不是对象"
                    else:
                        return payload
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                if allow_missing:
                    return None
                last_error = "清单还不存在(404)"
            else:
                last_error = f"HTTP {exc.code}"
        except OSError as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < attempts:
            time.sleep(min(3.0 * attempt, 15.0))
    raise RuntimeError(f"清单读不到 —— 试了 {attempts} 次: {last_error}")
