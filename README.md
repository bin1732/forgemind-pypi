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

[English](README.md) · [中文](README_zh.md)

</div>

---

## ✨ Features

| | |
|---|---|
| **166 Alpha Factors** | Alpha101 · Alpha158 · Barra risk model · IC monitoring |
| **Stock Screening Agent** | Multi-factor scoring + AI rationale generation |
| **Backtest Engine** | Vectorized · Monte Carlo · Walk-Forward · Slippage modeling |
| **AI Decision Agent** | LangGraph 3-Agent pipeline · 9 LLM providers · Human-in-the-loop gating |
| **Desktop App** | Tauri 2.x · Next.js 15 frontend · MCP protocol (Claude Desktop / Cursor) |
| **Free Data** | AKShare · A-shares · US · DuckDB local storage |

---

## 📦 Install

```bash
pip install forgemind
```

Or with Docker:

```bash
docker run -p 8000:8000 forgemind
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
│  166 Alpha Factors · IC Monitor · Risk Model           │
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
# 29 test files · 300+ tests · ~4 min
```

---

## 🤝 Contributing

PRs welcome. Please run `pre-commit run --all-files` before submitting.

---

## 📄 License

[Apache License 2.0](LICENSE) · Copyright 2026 灵感引擎工坊 (bin1732)
