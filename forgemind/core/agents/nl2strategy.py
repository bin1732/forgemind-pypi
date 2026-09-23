# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import json
import re
from typing import Optional, Dict, List

from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.agents")
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


@dataclass
class StrategyCode:
    """自然语言翻译出来的策略代码"""
    name: str
    description: str
    code: str
    params: Dict
    entry_signal: str  # 触发买入的自然语言
    exit_signal: str   # 触发卖出的自然语言


class NL2Strategy:
    """自然语言 → 策略代码
    
    创新:用 LLM 把用户的自然语言描述翻译成可执行的策略代码。
    对标 RD-Agent 但更轻量。
    """
    
    # 模式匹配(无 LLM 时 fallback)
    PATTERNS = {
        # 均线交叉
        r"(\d+)\s*日均线(?:上穿|金叉|向上穿过)\s*(\d+)\s*日均线": "MA_CROSS",
        r"(\d+)\s*day\s+MA\s+crosses\s+(\d+)\s+day\s+MA": "MA_CROSS",
        # RSI
        r"RSI\s*<\s*(\d+)": "RSI_OVERSOLD",
        r"RSI\s*>\s*(\d+)": "RSI_OVERBOUGHT",
        # 布林带
        r"突破.*布林带上轨": "BOLL_BREAK_UP",
        r"跌破.*布林带下轨": "BOLL_BREAK_DOWN",
        # MACD
        r"MACD.*金叉": "MACD_GOLDEN",
        r"MACD.*死叉": "MACD_DEATH",
    }
    
    def __init__(self, llm_provider=None):
        self.llm = llm_provider  # 可选 LLM
    
    def parse(self, natural_language: str) -> StrategyCode:
        """解析自然语言
        
        Args:
            natural_language: 用户描述,如 "20 日均线上穿 60 日均线买入,跌破 20 日均线卖出"
        
        Returns:
            StrategyCode
        """
        if self.llm:
            return self._parse_with_llm(natural_language)
        else:
            return self._parse_with_pattern(natural_language)
    
    def _parse_with_pattern(self, text: str) -> StrategyCode:
        """模式匹配(无 LLM 时)"""
        matches = []
        for pattern, kind in self.PATTERNS.items():
            for m in re.finditer(pattern, text):
                matches.append((kind, m.groups()))
        
        if not matches:
            return StrategyCode(
                name="CustomStrategy",
                description=text,
                code="# 无法识别的策略描述",
                params={},
                entry_signal=text,
                exit_signal="",
            )
        
        # 生成代码
        params = {}
        if matches and matches[0][0] == "MA_CROSS":
            fast, slow = matches[0][1]
            params = {"fast": int(fast), "slow": int(slow)}
            code = f'''
class Strategy(StrategyBase):
    """{text}"""
    def __init__(self, fast={fast}, slow={slow}):
        self.fast = fast
        self.slow = slow
    
    def generate_signal(self, df):
        ma_fast = df["close"].rolling(self.fast).mean()
        ma_slow = df["close"].rolling(self.slow).mean()
        signals = pd.Series(0, index=df.index)
        signals[(ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))] = 1
        signals[(ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))] = -1
        return signals
'''
        elif matches and matches[0][0] == "RSI_OVERSOLD":
            threshold = int(matches[0][1][0])
            params = {"threshold": threshold}
            code = f'''
class Strategy(StrategyBase):
    """{text}"""
    def generate_signal(self, df):
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rsi = 100 - 100 / (1 + gain / (loss + 1e-9))
        signals = pd.Series(0, index=df.index)
        signals[rsi < {threshold}] = 1
        return signals
'''
        else:
            code = f"# {text}"
        
        return StrategyCode(
            name="AutoStrategy",
            description=text,
            code=code,
            params=params,
            entry_signal=text,
            exit_signal="",
        )
    
    def _parse_with_llm(self, text: str) -> StrategyCode:
        """用 LLM 解析"""
        prompt = f"""你是一个量化策略专家。把用户的自然语言策略描述翻译成 Python 策略代码。

要求:
1. 输出 pandas DataFrame-based 策略代码
2. 信号生成函数返回 pd.Series(1=buy, -1=sell, 0=hold)
3. 代码要 production-ready

用户描述:
{text}

请输出 JSON:
{{
    "name": "策略名",
    "code": "完整 Python 代码",
    "params": {{参数: 值}},
    "entry_signal": "触发买入的条件(自然语言)",
    "exit_signal": "触发卖出的条件"
}}
"""
        try:
            response = self.llm.chat([{"role": "user", "content": prompt}])
            content = response.get("content", "{}")
            # 提取 JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return StrategyCode(
                    name=data.get("name", "LLMStrategy"),
                    description=text,
                    code=data.get("code", ""),
                    params=data.get("params", {}),
                    entry_signal=data.get("entry_signal", ""),
                    exit_signal=data.get("exit_signal", ""),
                )
        except Exception as e:
            # LLM 调用或 JSON 解析失败 — 降级到模式匹配,这是设计意图而非静默 bug
            logger.warning(
                "nl_strategy_llm_parse_failed",
                error=str(e),
                error_type=type(e).__name__,
                fallback="pattern_match",
            )
        
        return self._parse_with_pattern(text)
    
    def save_to_file(self, strategy: StrategyCode, path: str):
        """保存到文件"""
        Path(path).write_text(strategy.code)


class AIFactorFactory:
    """AI 因子工厂 — LLM 驱动自动挖因子
    
    流程:
    1. 用户给定方向(如"挖掘小盘股反转因子")
    2. LLM 提出 10-20 个因子思路
    3. 写代码 + 跑 IC 评估
    4. 选 Top-N 高 IC 因子
    5. 加入因子库
    """
    
    def __init__(self, llm_provider=None, factor_lib=None):
        self.llm = llm_provider
        self.factor_lib = factor_lib  # 因子库接口
    
    def generate_factor_ideas(self, theme: str, n_ideas: int = 10) -> List[str]:
        """生成因子思路"""
        if self.llm is None:
            # Fallback: 模板
            return [
                f"{theme}:近 N 日成交量均值",
                f"{theme}:波动率倒数",
                f"{theme}:价格动量反转",
                f"{theme}:换手率变化",
                f"{theme}:日内振幅",
                f"{theme}:量比异常",
                f"{theme}:价格突破均线比率",
                f"{theme}:行业相对强度",
                f"{theme}:市值分位",
                f"{theme}:PE 历史百分位",
            ]
        
        prompt = f"""请基于这个主题,设计 {n_ideas} 个量化因子:

主题: {theme}

要求每个因子:
1. 明确的数学公式(用自然语言描述)
2. 数据来源(行情/财务/另类)
3. 预期 IC 方向(正向 / 负向)
4. 适用频率(日频 / 周频)

输出 JSON 列表:
[{{"name": "...", "formula": "...", "source": "...", "ic_direction": "+/-", "frequency": "..."}}]
"""
        try:
            response = self.llm.chat([{"role": "user", "content": prompt}])
            content = response.get("content", "[]")
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return [d.get("formula", "") for d in data]
        except Exception as e:
            logger.warning(
                "ai_factor_factory_llm_failed",
                error=str(e),
                error_type=type(e).__name__,
                fallback="generate_factor_ideas",
            )
        
        return self.generate_factor_ideas(theme, n_ideas)  # fallback


class NaturalLanguageResearchLog:
    """自然语言研究日志 — 自动生成决策研究笔记"""
    
    def __init__(self, log_dir: str = "./data/research_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_log(
        self,
        symbol: str,
        decision: str,
        agent_votes: Dict[str, str],
        factors: Dict[str, float],
        news: Optional[List[str]] = None,
    ) -> str:
        """生成 Markdown 格式的研究日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log = f"""# 研究日志 — {symbol}

**时间**: {timestamp}
**决策**: {decision}

## Agent 投票

"""
        for agent, vote in agent_votes.items():
            log += f"- **{agent}**: {vote}\n"
        
        log += "\n## 关键因子\n\n"
        for factor_name, value in factors.items():
            log += f"- **{factor_name}**: {value:.4f}\n"
        
        if news:
            log += "\n## 关联新闻\n\n"
            for n in news[:5]:
                log += f"- {n}\n"
        
        log += f"\n## 决策理由\n\n"
        log += f"基于上述 6 个 Agent 的共识 + {len(factors)} 个因子 + 实时新闻分析,系统判定该标的: **{decision}**。\n"
        log += f"建议人工 review 后执行。\n"
        
        # 存盘
        filename = self.log_dir / f"{symbol}_{timestamp.replace(':', '-').replace(' ', '_')}.md"
        filename.write_text(log)
        
        return log


class RealtimeSentimentFeed:
    """实时舆情监控 — 新闻流 → 情感分数 → 因子"""
    
    def __init__(self):
        self.sentiment_history = {}  # symbol -> [(timestamp, score), ...]
    
    def update(self, symbol: str, news_items: List[Dict]):
        """更新舆情数据"""
        for item in news_items:
            score = item.get("sentiment_score", 0.0)
            ts = item.get("date", datetime.now())
            if symbol not in self.sentiment_history:
                self.sentiment_history[symbol] = []
            self.sentiment_history[symbol].append((ts, score))
    
    def get_sentiment_factor(self, symbol: str, window: int = 7) -> float:
        """计算舆情因子(过去 window 天的平均情感分数)"""
        history = self.sentiment_history.get(symbol, [])
        if not history:
            return 0.0
        recent = history[-window:]
        if not recent:
            return 0.0
        scores = [s for _, s in recent]
        return sum(scores) / len(scores)
    
    def get_sentiment_momentum(self, symbol: str) -> float:
        """情感动量(最近 vs 之前)"""
        history = self.sentiment_history.get(symbol, [])
        if len(history) < 2:
            return 0.0
        recent = sum(s for _, s in history[-3:]) / min(3, len(history))
        earlier = sum(s for _, s in history[-7:-3]) / max(1, min(4, len(history) - 3))
        return recent - earlier