# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import tempfile
from pathlib import Path


class TestNL2Strategy:
    def test_parse_ma_cross(self):
        from forgemind.core.agents import NL2Strategy
        parser = NL2Strategy()  # 无 LLM,模式匹配
        result = parser.parse("20 日均线上穿 60 日均线买入,跌破 20 日均线卖出")
        assert result.code is not None
        assert "rolling" in result.code
        assert 20 in result.params.values() or 60 in result.params.values()
    
    def test_parse_rsi(self):
        from forgemind.core.agents import NL2Strategy
        parser = NL2Strategy()
        result = parser.parse("RSI < 30 买入")
        assert "rsi" in result.code.lower() or "RSI" in result.code
    
    def test_save_to_file(self):
        from forgemind.core.agents import NL2Strategy
        parser = NL2Strategy()
        result = parser.parse("20 日均线上穿 60 日均线")
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            path = f.name
            parser.save_to_file(result, path)
            content = Path(path).read_text()
            assert "rolling" in content


class TestAIFactorFactory:
    def test_generate_factor_ideas(self):
        from forgemind.core.agents import AIFactorFactory
        factory = AIFactorFactory()  # 无 LLM
        ideas = factory.generate_factor_ideas("小盘股反转", n_ideas=5)
        assert len(ideas) >= 5
        assert all(isinstance(i, str) for i in ideas)


class TestNaturalLanguageResearchLog:
    def test_generate_log(self):
        from forgemind.core.agents import NaturalLanguageResearchLog
        
        with tempfile.TemporaryDirectory() as tmp:
            log = NaturalLanguageResearchLog(log_dir=tmp)
            content = log.generate_log(
                symbol="600519.SH",
                decision="BUY",
                agent_votes={"Fundamentals": "买入(4/5)", "Technical": "中性(3/5)"},
                factors={"RSI": 45.2, "MACD_DIF": 0.15},
                news=["茅台发布新产品"],
            )
            assert "# 研究日志" in content
            assert "600519.SH" in content
            assert "BUY" in content
            assert "RSI" in content
            assert "茅台" in content
            
            # 检查文件已存
            files = list(Path(tmp).glob("*.md"))
            assert len(files) >= 1


class TestRealtimeSentimentFeed:
    def test_update_and_get_factor(self):
        from forgemind.core.agents import RealtimeSentimentFeed
        feed = RealtimeSentimentFeed()
        
        news = [
            {"date": "2024-01-01", "sentiment_score": 0.5},
            {"date": "2024-01-02", "sentiment_score": -0.3},
            {"date": "2024-01-03", "sentiment_score": 0.8},
        ]
        feed.update("600519.SH", news)
        
        score = feed.get_sentiment_factor("600519.SH", window=7)
        # 平均 ≈ 0.333
        assert -1 <= score <= 1
        assert score > 0
    
    def test_sentiment_momentum(self):
        from forgemind.core.agents import RealtimeSentimentFeed
        feed = RealtimeSentimentFeed()
        
        news = [
            {"date": "2024-01-01", "sentiment_score": -0.5},
            {"date": "2024-01-02", "sentiment_score": -0.3},
            {"date": "2024-01-03", "sentiment_score": 0.8},
            {"date": "2024-01-04", "sentiment_score": 0.9},
        ]
        feed.update("600519.SH", news)
        momentum = feed.get_sentiment_momentum("600519.SH")
        assert momentum > 0  # 最近比之前更正面


class TestIntegration:
    def test_nl2strategy_to_backtest(self):
        """NL2Strategy 输出代码, 模拟运行"""
        from forgemind.core.agents import NL2Strategy
        
        parser = NL2Strategy()
        result = parser.parse("5 日均线上穿 10 日均线买入,跌破 5 日均线卖出")
        
        # 代码应该是合法的 Python(可以解析为 AST)
        import ast
        try:
            ast.parse(result.code)
        except SyntaxError:
            pytest.fail("生成的策略代码语法错误")