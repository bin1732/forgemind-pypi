# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""US 数据源 — 可插拔骨架

设计原则:
  - 没有任何「免费、不限流、全球可达」的 US K 线 API。
    已验证 Yahoo v8 = 429、Stooq = 404、新浪美股 = 接口已废弃、
    雪球 = 沙箱黑名单、腾讯 = 只返回首末两点。
    所以默认这个 source 在没 token 时返回 actionable 错误,
    而不是装作能跑。
  - 需要 token 时,落 Polygon.io(免费 5 req/min)。
  - 接受环境变量 FORGEMIND_US_PROVIDER / FORGEMIND_US_TOKEN。
"""

from __future__ import annotations

import os
import ssl
import urllib.error
import urllib.request
from typing import Any  # noqa: I001

import pandas as pd

from forgemind.core.data.sources.extended_sources import (
    DataSource,
    DataSourceUnavailableError,
)

logger = __import__("structlog").get_logger("forgemind.us_source")


# 这些 401/403/429 不是「网络错」而是「没 token / 限流」,
# 抛一个单独的 actionable 错(带链接 + 下一步)。
class USAuthError(RuntimeError):
    """US 数据源需要 token,或 token 错误/被限流

    显式不继承 DataSourceUnavailableError,因为后者要求 (source, reason)
    两参数,而 USAuthError 的语义更窄(US-specific auth),自己 hold 一段
    完整的指引文本更方便直接展示给用户。
    """


class USDataSource(DataSource):
    """美股 K 线数据源

    免费数据源都已测试不可用(详见模块 docstring)。
    默认接受 token 类源:
      • polygon.io(免费 5 req/min,推荐)
      • tiingo(免费 50 req/day)
    设置:
      FORGEMIND_US_PROVIDER=polygon  (默认)
      FORGEMIND_US_TOKEN=<your_token>
    """

    PROVIDERS = {"polygon", "tiingo"}

    def __init__(self) -> None:
        self.provider = os.environ.get("FORGEMIND_US_PROVIDER", "polygon").lower()
        self.token = os.environ.get("FORGEMIND_US_TOKEN", "").strip()

    def _check_ready(self) -> None:
        if self.provider not in self.PROVIDERS:
            raise USAuthError(f"未知的 US provider={self.provider!r};可选:{sorted(self.PROVIDERS)}")
        if not self.token:
            raise USAuthError(
                "未配置 FORGEMIND_US_TOKEN。"
                "美股 K 线没有免费不限流的公开源 —— "
                "Polygon.io 免费层 5 req/min: https://polygon.io/,"
                "Tiingo 免费层 50 req/day: https://www.tiingo.com/,"
                "注册后把 token 设到环境变量 FORGEMIND_US_TOKEN 再重试。"
            )

    async def get_history(
        self,
        symbol: str,
        start: str = "2024-01-01",
        end: str = "2024-12-31",
        adjust: str = "",
        period: str = "daily",
    ) -> pd.DataFrame:
        """拉美股 K 线;无 token 时返回 actionable 错误而不是堆栈"""
        self._check_ready()
        try:
            if self.provider == "polygon":
                return await self._polygon_history(symbol, start, end)
            if self.provider == "tiingo":
                return await self._tiingo_history(symbol, start, end)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise USAuthError(
                    f"{self.provider} 拒绝:{exc.code};"
                    "检查 FORGEMIND_US_TOKEN 是否有效,"
                    "或免费 tier 是否已耗尽"
                ) from exc
            if exc.code == 429:
                raise USAuthError(
                    f"{self.provider} 限流 (HTTP 429):"
                    "免费 tier 速率限制 —— 等待后重试,"
                    "或升级付费 tier"
                ) from exc
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DataSourceUnavailableError(
                f"{self.provider} 网络不通:{type(exc).__name__}:{exc};"
                "美股源通常需要从能访问 global internet 的网络调"
            ) from exc

        raise USAuthError(f"未实现 provider={self.provider}")

    async def _polygon_history(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        s = start.replace("-", "")
        e = end.replace("-", "")
        url = (
            f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}"
            f"/range/1/day/{s}/{e}?apiKey={self.token}"
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(url, timeout=20, context=ctx) as r:
            import json

            data = json.loads(r.read())
        rows = data.get("results") or []
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        # Polygon: t=timestamp ms, o/h/l/c/v
        df["date"] = pd.to_datetime(df["t"], unit="ms").dt.strftime("%Y-%m-%d")
        df["symbol"] = symbol.upper()
        return df.rename(
            columns={
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
            }
        )[["date", "symbol", "open", "high", "low", "close", "volume"]]

    async def _tiingo_history(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        url = (
            f"https://api.tiingo.com/iex/{symbol.lower()}"
            f"?startDate={start}&endDate={end}&format=csv"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Token {self.token}",
                "Content-Type": "text/csv",
            },
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            body = r.read().decode()
        df = pd.read_csv(pd.io.common.StringIO(body))
        if df.empty:
            return df
        df = df.rename(
            columns={
                "date": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        )
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df["symbol"] = symbol.upper()
        return df[["date", "symbol", "open", "high", "low", "close", "volume"]]

    async def get_stock_list(self) -> pd.DataFrame:
        """美股列表 — 仅当有 token 时才能拿到"""
        self._check_ready()
        return pd.DataFrame()  # 留给上层实现 / mock

    async def fetch(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """DataSource 抽象方法的占位 — US 走 get_history 更直接"""
        raise NotImplementedError("USDataSource.fetch 不直接被调用,使用 get_history(symbol=...)")

    async def get_schema(self) -> dict[str, Any]:
        """DataSource 抽象方法 — 描述这个源能给的字段"""
        return {
            "provider": self.provider,
            "asset_class": "us_equities",
            "columns": ["date", "symbol", "open", "high", "low", "close", "volume"],
            "token_required": True,
        }
