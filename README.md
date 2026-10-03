<div align="center">

# 🧠 ForgeMind

**AI-Powered Quantitative Research & Trading Agent Framework**

*Build, test, and deploy quantitative strategies with AI agents — no 50-engineer team required.*

</div>

<div align="center">

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/downloads/)
[![Tauri](https://img.shields.io/badge/Tauri-2.x-orange.svg)](https://tauri.app/)
[![Stars](https://img.shields.io/github/stars/bin1732/forgemind?style=social)](https://github.com/bin1732/forgemind)

[English](README.md) · Apache-2.0

</div>

---

## ✨ Features

| | |
|---|---|
| **166 Alpha Factors** | Alpha158 (149) · Alpha101 (17) · Barra 风险模型 · IC 监控 |
| **Stock Screening Agent** | Multi-factor scoring + AI rationale generation |
| **Backtest Engine** | Event-driven · Walk-Forward optimizer · Monte Carlo · 3 种滑点模型 |
| **AI Decision Agent** | LangGraph 6-node pipeline · 9 LLM providers · 人工审批 gating |
| **Desktop App** | Tauri 2.x · Next.js 15 frontend · MCP protocol (Claude Desktop / Cursor) |
| **Free Data** | AKShare · A-shares · US · DuckDB local storage |

---

## 📦 Install

```bash
# 从 GitHub Pages 索引安装
#
# 必须是 --extra-index-url,不是 --index-url:
#   --index-url 会**替换**默认源,于是 fastapi / duckdb 这些依赖也去
#   我们的索引里找,结果全部 "No matching distribution found"。
#   --extra-index-url 是在默认源(PyPI)旁边**追加**我们的索引,依赖照常
#   从 PyPI 解析,forgemind 本体从我们的索引拿。
#
# 同理,地址是 /pypi/simple/,**不要**再带 /forgemind/ ——
# pip 会自动拼接项目名,写成 .../simple/forgemind/ 时它实际请求
# .../simple/forgemind/forgemind/ 得到 404。
pip install --extra-index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/ forgemind

# 需要 A 股数据源(forgemind etl)时,加 [cn] extra:
pip install --extra-index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/ "forgemind[cn]"
```

> 验证方式:以上两条命令在全新 venv 中实测通过 —— `--extra-index-url` 形式
> 能同时解析 forgemind 本体与全部依赖,`forgemind[cn]` 额外装上 akshare。
> 也可直接装文件:`pip install forgemind-2026.9.3-py3-none-any.whl`

或直接下载单文件二进制(Linux / macOS / Windows,见 Releases)。

启动本地 API 服务:

```bash
forgemind mcp            # MCP server(stdio,可接 Claude Desktop / Cursor)
python -m forgemind.api.main --port 8000
```

**Requirements:** Python 3.11+ · AKShare (free data) · Optional: OpenAI / Anthropic API key

---

## 🚀 Quick Start

```python
from forgemind.core.agents.stock_picker import StockPickerAgent
from forgemind.core.data.akshare_etl import AKShareETL
from forgemind.core.backtest.engine import SimpleBacktestEngine

# 1. Pull free A-share data
etl = AKShareETL()
await etl.run(symbols=["600519", "000001"], start="2024-01-01")

# 2. Screen with multi-factor agent
picker = StockPickerAgent()
picks = await picker.pick(universe=["600519", "000001"], top_n=5)

# 3. Backtest
from forgemind.core.strategies.base import MovingAverageCrossStrategy
engine = SimpleBacktestEngine(initial_capital=100_000)
result = engine.run(MovingAverageCrossStrategy(), price_df)
print(result.sharpe, result.total_return, result.max_drawdown)

# 4. AI decision (Claude / GPT / Ollama)
from forgemind.core.agents.portfolio_context import run_decision
state = await run_decision(symbol="600519.SH", portfolio=PortfolioContext(...))
```

Or via CLI:

```bash
# etl / pick 需要 A 股数据源,先确保装了 [cn] extra(akshare)
forgemind etl --symbols 600519,000001 --start 2024-01-01
forgemind pick --top-n 5
forgemind backtest --strategy ma_cross
forgemind agent --symbol 600519.SH
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   ForgeMind                             │
├──────────────┬──────────────────┬─────────────────────┤
│  CLI / API   │  Desktop (Tauri) │  MCP Protocol       │
├──────────────┴──────────────────┴─────────────────────┤
│  FastAPI Server                                        │
├───────────────┬───────────────┬───────────────────────┤
│  Stock Picker │  AI Decision  │  Backtest Engine       │
│  Agent        │  (LangGraph)  │  (Vectorized)         │
├───────────────┴───────────────┴───────────────────────┤
│  166 Alpha Factors (Alpha158 + Alpha101) · IC · Barra  │
├─────────────────────────────────────────────────────────┤
│  AKShare ETL → DuckDB / ClickHouse                    │
└─────────────────────────────────────────────────────────┘
```

---

## 🤖 LLM Providers

**9 providers** with automatic fallback:

> OpenAI · Anthropic · Google Gemini · DeepSeek · Qwen · Mistral · Ollama · vLLM · LM Studio

Default fallback chain: Claude → GPT → Gemini → DeepSeek → Ollama.

---

## 📡 Signals

ForgeMind outputs trading signals — it does **not** connect to brokers. Use the signal JSON with your own execution layer (vnpy · nautilus_trader · broker SDK).

```json
{
  "signal_id": "sig_20260919_141532_600519.SH",
  "symbol": "600519.SH",
  "side": "BUY",
  "confidence": 0.78,
  "rationale": "Multi-agent consensus: fundamentals 4/5, technical 3/5, sentiment 5/5",
  "timestamp": "2026-09-19T14:15:32Z",
  "execution": "USER_RESPONSIBILITY"
}
```

---

## 🧪 Tests

```bash
pytest tests/ -v
# 47 test files · 450+ tests · ~6 min
```

---

## 🤝 Contributing

PRs welcome. Please run `pre-commit run --all-files` before submitting.

---

## 📄 License

[Apache License 2.0](LICENSE) · Copyright 2026 灵感引擎工坊 (bin1732)
