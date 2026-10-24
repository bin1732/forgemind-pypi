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
| **169 Alpha Factors** | Alpha158 (152) · Alpha101 (11) · Barra 风险模型 · IC 监控 |
| **Stock Screening Agent** | Multi-factor scoring + AI rationale generation |
| **Backtest Engine** (`forgemind backtest`) | Event-driven 事件驱动 · 3 种滑点模型(fixed / linear / sqrt) · 17 策略(`forgemind backtest --list-strategies` 看全部) |
| **AI Decision Agent** | LangGraph 6-node pipeline · 9 LLM providers · 人工审批 gating |
| **Desktop App** | Tauri 2.x · Next.js 15 frontend · MCP protocol (Claude Desktop / Cursor) — 需本机已装 Python 3.11+ 与本包(桌面端启动 Python sidecar,未捆绑解释器) |
| **Free Data** | AKShare · A-shares + CN macro(PMI / CPI / PPI / M2 / 国债收益率 / 汇率)· DuckDB · *(US 需配置 FORGEMIND_US_TOKEN,见 `forgemind info`)* |

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

> 验证方式:以上两条命令在全新 venv 中已验证通过 —— `--extra-index-url` 形式
> 能同时解析 forgemind 本体与全部依赖,`forgemind[cn]` 额外装上 akshare。
> 也可直接装文件:从上面的下载页取 `forgemind-<版本>-py3-none-any.whl` 再 `pip install` 它。

或直接下载单文件二进制(Linux / macOS / Windows,见 Releases)。

启动本地 API 服务:

```bash
python -m forgemind.api.main --port 8000
```

**Requirements:** Python 3.11+ · AKShare (free data) · Optional: OpenAI / Anthropic API key

**Optional services:** ClickHouse / PostgreSQL / Redis / NATS 是多租户生产环境的可选项,本地单机跑 DuckDB 即可。`/api/v1/health/services` 会报这些 service 的连接状态 —— **未连接不影响** `forgemind etl / pick / backtest / agent / mcp` 任何子命令。

---

## 🔬 Research Pipeline(API / Tauri 桌面端)

`forgemind backtest` 跑的是事件驱动回测。完整研究流水线(**Walk-Forward Optimization · Monte Carlo 稳健性 · 多因子 IC 评估 · LightGBM 训练**)在 `POST /api/v1/pipeline/run`(Tauri 桌面端专用)与 `forgemind.core.pipeline.EndToEndPipeline` Python SDK 中提供;CLI 子命令未单独暴露。

装好之后可以直接跑一次研究流程,结果来自真实数据:

```bash
python scripts/research_demo.py --symbols 600519,000001 --start 2024-01-01
```

它会依次完成取数、因子 IC 评估、选股与回测,并打印可分析的结果。
加 `--json` 可以拿到结构化输出。

## 🔌 接入 MCP 客户端(Claude Desktop / Cursor / Claude Code)

`forgemind mcp` 以 stdio 方式提供 10 个 MCP 工具。客户端需要一个**绝对路径**
的命令 —— MCP 客户端不会用你当前 shell 的 PATH。

**1. 确认 `forgemind` 在哪**

```bash
which forgemind     # macOS/Linux
where forgemind     # Windows
```

**2. 写进客户端配置**

`claude_desktop_config.json`(macOS:
`~/Library/Application Support/Claude/`;Windows:
`%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "forgemind": {
      "command": "/abs/path/to/forgemind",
      "args": ["mcp"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

Cursor / Claude Code 等把 `mcpServers` 放在各自配置里,结构相同。

**3. 验证连上了**

客户端里问一句"列一下 forgemind 有哪些工具",或直接手动握手:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  | forgemind mcp
```

应回 `{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"forgemind",...}}}`

> **用真实数据**:客户端里的 `get_kline` / `stock_pick` / `check_ic_decay`
> 读的是本地 DuckDB,得先跑过一次 `forgemind etl`,否则会如实返回
> "本地没有行情数据"。

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
│ CLI / API    │ Desktop (Tauri)  │ MCP Protocol        │
├──────────────┴──────────────────┴─────────────────────┤
│  FastAPI Server                                         │
├───────────────┬───────────────┬───────────────────────┤
│ Stock Picker  │ AI Decision   │ Backtest Engine       │
│ Agent         │ (LangGraph)   │ (Event-driven)        │
├───────────────┴───────────────┴───────────────────────┤
│  169 Alpha Factors (Alpha158 + Alpha101) · IC · Barra   │
├─────────────────────────────────────────────────────────┤
│  AKShare ETL → DuckDB / ClickHouse                      │
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

## 🧪 Verify Your Install

装完之后先确认包本身可用:

```bash
forgemind info                      # 版本、数据源、连接状态
forgemind backtest --list-strategies # 可用策略清单
forgemind mcp                       # 以标准输入输出的方式启动 MCP 服务
```

发布出去的每一个构件都经过下面这些检查,全部在可复现的流水线里完成:

| 检查 | 内容 | 流水线 / 作业 |
| --- | --- | --- |
| 构件构建 | 从源码构建 wheel 与源码包,校验安装后能导入 | `verify.yml` / verify-wheel |
| 命令行冒烟 | 逐个执行全部子命令,确认退出码与输出 | `verify.yml` / verify-wheel |
| 接口校验 | 真实起服务,逐个请求接口,校验参数校验与错误响应 | `verify.yml` / verify-wheel |
| 真实取数 | 拉真实行情并落库,确认多源回退可用 | `verify-live.yml` / live-akshare |
| 桌面端 | 下载发布出来的三个平台二进制并实跑,确认能启动 | `verify-desktop.yml` / build-desktop |
| 用户旅程 | 从公开索引页出发:下载、核对校验值、装进干净环境、跑命令、握 MCP 协议 | `verify.yml` / 真实用户旅程 |
| 全量门禁 | 镜像源码仓的代码质量、安全扫描、全量测试(含重并发档)与界面测试 | `ci-mirror.yml` / 镜像 · Python 测试 (常规) |
| 重并发完整规模 | 关掉按文件分组抽样，把重并发档的全部用例完整跑一遍 | `ci-heavy-full.yml` / 重并发测试 (完整规模) |
| 装出来的构件 | 下载发布出去的那一个 wheel,装进干净环境,把全量测试跑在上面 | `ci-mirror.yml` / 镜像 · 全量测试跑在发布出去的 wheel 上 |

除冒烟之外,这里还**镜像**了源码仓的整套门禁 —— 代码质量、安全扫描、
全量测试(含重并发档)、界面测试,跑的都是源码仓 main,也就是"即将发布的
那一份提交"。镜像的完整性由 `scripts/check_ci_mirror.py` 核对:源码仓
每一条检查命令都必须在镜像里出现,少一条就报错;源码仓里无条件执行的
检查,也不许在镜像里被条件跳过。

重并发档在流水线上按文件分组抽样(每个文件留一个代表),完整规模另有
一个作业专门跑 —— 规模是那批用例的设计意图,抽样只是机器跑不完时的
妥协。

还有一档把全量测试跑在**装出来的 wheel**上:别的作业验的是源码树,
用户装到的是 wheel,这是两句话。装出来再跑,这句话就不用说了 ——
发布出去的依赖区间是不是用得了,也只有这样才验得出来。

桌面端构件从 [Releases](https://github.com/bin1732/forgemind-pypi/releases) 下载。
运行中的探测脚本在 `scripts/live_probe.py`,对着已安装的包执行:

```bash
python scripts/live_probe.py
```

用户旅程的验证脚本在 `scripts/verify_user_journey.py`,它不碰本地源码,
只从公开索引页取构件,自己装、自己跑:

```bash
python scripts/verify_user_journey.py
```

---

## 🤝 Contributing

本仓库是发布与验证仓,收录安装说明、下载索引、验证脚本与发布流水线。
面向使用者的改动(文档、验证、发布流程)欢迎提 PR,流程见
[CONTRIBUTING.md](.github/CONTRIBUTING.md)。包的源码不在本仓库,
功能与缺陷讨论请在 [Issues](https://github.com/bin1732/forgemind-pypi/issues) 发起。

---

## 📄 License

[Apache License 2.0](LICENSE) · Copyright 2026 灵感引擎工坊 (bin1732)
