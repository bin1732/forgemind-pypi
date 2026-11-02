# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""数据源与模型不得用随机数冒充真实数据

发现的四个编造点,全部返回**字段齐全、数值合理**的数据,调用方无从分辨:

  | 位置 | 编造内容 | 危害 |
  |---|---|---|
  | TushareProSource | PE/PB/PS/换手率 np.random.uniform(5,50) | 估值判断直接建立在假数字上 |
  | NewsDataSource | 标题 "600519.SH 出现新闻标题 847"、example.com | 情绪信号驱动交易决策 |
  | SectorDataSource | 行业 np.random.choice 8 选 1 | 行业中性化 IC 分错组 |
  | EmbeddingsModel | np.random.randn 冒充语义向量 | 随机向量等距,检索退化为随机排序 |

共同点:**都不崩,都返回正常的 DataFrame/ndarray,只是内容是编的。**
这与"import 成功""返回了 JSON"是同一类陷阱 —— 接口正常不等于干了活。
"""

import ast
import re
from pathlib import Path

import pytest
from _path_setup import child_env

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "forgemind"


def _module(name: str):
    import importlib

    return importlib.import_module(name)


class TestSourcesRefuseInsteadOfFabricating:
    def test_tushare_without_token_refuses(self):
        m = _module("forgemind.core.data.sources.extended_sources")
        s = m.TushareProSource(token="")
        ok, why = s.is_available()
        assert not ok
        assert "TUSHARE_TOKEN" in why, "必须告诉用户怎么解决"
        with pytest.raises(m.DataSourceUnavailableError):
            s.fetch(["600519.SH"], "2024-01-01", "2024-01-31")

    def test_tushare_with_token_is_available(self):
        m = _module("forgemind.core.data.sources.extended_sources")
        s = m.TushareProSource(token="dummy-token-for-availability-check")
        ok, _ = s.is_available()
        # 有 token 且装了 tushare 才算可用;环境没装时应报"未安装"而非"缺 token"
        assert ok or "未安装" in s.is_available()[1]

    # 各源的 fetch 签名不同,不能一套参数打天下
    # 宏观源已经接到公开接口上,不再属于这一类;它的取值必须等于接口
    # 给的数,由 tests/test_macro_data_source.py 守着。
    UNIMPLEMENTED = {
        "NewsDataSource": (["600519.SH"], "2024-01-01", "2024-01-10"),
        "SectorDataSource": (["600519.SH"],),
    }

    @pytest.mark.parametrize("cls_name", sorted(UNIMPLEMENTED))
    def test_unimplemented_sources_refuse(self, cls_name):
        m = _module("forgemind.core.data.sources.extended_sources")
        s = getattr(m, cls_name)()
        ok, why = s.is_available()
        assert not ok, f"{cls_name} 声称可用,但并没有真实实现"
        assert len(why) > 20, "不可用原因要能指导用户下一步"
        with pytest.raises(m.DataSourceUnavailableError):
            s.fetch(*self.UNIMPLEMENTED[cls_name])

    def test_embedding_refuses_instead_of_random_vectors(self):
        m = _module("forgemind.core.multimodal.embedding")
        emb = m.EmbeddingsModel()
        try:
            out = emb.embed(["测试文本"])
        except m.EmbeddingModelUnavailableError:
            return  # 正确
        # 若模型确实装了,检查返回的不是随机向量
        assert emb.model is not None, (
            "模型未加载却返回了向量 —— 之前的 fallback 是 np.random.randn,"
            "随机向量两两等距,相似度检索等于随机排序")

    def test_empty_result_keeps_schema(self):
        """真实'没数据'要返回带 schema 的空表,而不是几行假数据"""
        m = _module("forgemind.core.data.sources.extended_sources")
        empty = m._empty_like_schema({"a": "str", "b": "float"})
        assert empty.height == 0
        assert empty.columns == ["a", "b"]


class TestNoFabricationGeneratorsRemain:
    """扫描:数据源与模型层不允许再出现随机填充

    正当用途要显式豁免:
      - Monte Carlo 的参数扰动(扰动本身就是目的)
      - 影子盘的模拟撮合
      - data_source="mock" 的演示数据(调用方显式声明)
    """

    # 文件 -> 允许出现随机数的理由
    ALLOWED = {
        "core/backtest/advanced.py": "蒙特卡洛参数扰动,扰动即目的",
        "core/live/shadow.py": "影子盘模拟撮合,不是真实成交",
        "core/pipeline/end_to_end.py": "data_source='mock' 显式标注的演示数据",
    }

    # 演示数据生成器:随机数是正当用途(没接真实数据源时的占位),
    # 但**必须**在输出里标明是模拟数据,否则用户会把 Total Return
    # 当成真实回测结果。豁免的是"生成",不是"冒充"。
    # 演示数据生成器:随机数是正当用途,但返回值必须自我声明是合成的。
    # 豁免的是"生成",不是"冒充" —— 由 TestDemoResultsAreLabelled 把关。
    DEMO_GENERATORS = {
        "forgemind/cli.py",
        "forgemind/api/main.py",
        "forgemind/core/pipeline/end_to_end.py",
        "forgemind/mcp/server.py",
    }

    _PAT = re.compile(
        r"np\.random\.(?:uniform|choice|randn|normal)\s*\(|default_rng\s*\(")

    def test_no_random_fill_in_data_or_model_layers(self):
        """扫描真正执行的代码,而不是"看起来像代码"的行

        两个易错点:
        1. 只按行首字符跳注释/docstring —— docstring 续行不以引号开头,
           里面的 "np.random.randn(...)" 会被误报。
        2. 改用 AST 收集所有字符串常量的行号来排除 —— **更糟**。
           真正的编造写法恰恰是 np.random.choice(["银行", "医药"]),
           字符串字面量就在代码行上,整行被当成 docstring 跳过,
           于是这个 bug 类永远抓不到。
        正确做法:用 tokenize 判断**匹配位置**是否落在 STRING/COMMENT
        记号内,而不是按行排除。
        """
        import io
        import tokenize

        offenders = []
        for path in SRC.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if any(rel.endswith(a) for a in self.ALLOWED):
                continue
            if rel in self.DEMO_GENERATORS:
                continue
            text = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            # 记下每个 STRING / COMMENT 记号覆盖的 (行, 列区间)
            spans: list[tuple[int, int, int, int]] = []
            try:
                for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                    if tok.type in (tokenize.STRING, tokenize.COMMENT):
                        spans.append((tok.start[0], tok.start[1],
                                      tok.end[0], tok.end[1]))
            except tokenize.TokenError:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                for m in self._PAT.finditer(line):
                    col = m.start()
                    inside = any(
                        (sl == i and sc <= col < ec) or (sl < i <= el)
                        for sl, sc, el, ec in spans)
                    if not inside:
                        offenders.append(f"{rel}:{i}: {line.strip()[:70]}")
                        break
        assert not offenders, (
            "数据/模型层又出现了随机填充,这些数字会被当成真实数据:\n  "
            + "\n  ".join(offenders))

    def test_mock_generator_absent_from_sources(self):
        src = (SRC / "core/data/sources/extended_sources.py").read_text(
            encoding="utf-8")
        assert "_mock_fundamental" not in src, "数据源里的 mock 构造函数应已删除"
        assert "_mock_news" not in src
        assert "_mock_macro" not in src


class TestDemoResultsAreLabelled:
    """CLI / API 用合成数据跑回测是可以的,但输出必须标明

    `forgemind backtest` 在没有真实数据时用 np.random 生成行情,然后打印
    "Total Return: 12.34%"。没有任何迹象表明这是模拟结果 —— 用户会
    当成真实回测。同理适用于 API 的 demo 分支。
    """

    def test_cli_marks_synthetic_backtest(self):
        import subprocess
        import sys

        r = subprocess.run(
            [sys.executable, "-m", "forgemind.cli", "backtest",
             "--strategy", "ma_cross", "--start", "2024-01-01", "--end", "2024-02-01"],
            capture_output=True, text=True, timeout=300,
            env=child_env())
        out = r.stdout + r.stderr
        assert "Total Return" in out, "回测应仍能跑出结果"
        assert re.search(r"模拟|合成|demo|Demo|非真实|随机", out), (
            "打印 Total Return 却不说数据是合成的,等同于编造:\n"
            + out[-400:])


class TestMcpBacktestIsLabelled:
    """MCP run_backtest 的输入是合成行情,返回值必须自我声明"""

    def test_declares_synthetic_and_not_real(self):
        import asyncio

        from forgemind.mcp.server import ForgeMindMCPServer

        r = asyncio.run(ForgeMindMCPServer()._tool_run_backtest(
            strategy="ma_cross", symbol="600519.SH",
            start="2024-01-01", end="2024-03-01", params={}))
        assert r.get("is_real_data") is False, r
        assert "synthetic" in str(r.get("data_source", "")).lower(), r
        assert "warning" in r and len(r["warning"]) > 20, (
            "必须带一句明确的警告,调用方(LLM)不会去猜 data_source 的含义")
