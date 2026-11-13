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
| **Backtest Engine** (`forgemind backtest`) | Event-driven 事件驱动 · 3 种滑点模型(fixed / linear / sqrt) · 9 个策略这条命令跑得起来(`forgemind backtest --list-strategies` 看全部,以及另一些策略为什么跑不了) |
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

> **每次发布的版本号带一个递增的 post 号**(2026.9.3 → 2026.9.3.post1 →
> 2026.9.3.post2 → …),所以 `pip install --upgrade` 能正常升级到新发布的
> 构建。版本号写在每次发布的清单里(`releases/builds/manifest.json` 的
> `published_version`),发布出去的 wheel 文件名与它一致。
>
> 为什么要 post 号:同一个版本号下内容变了,pip 是不会升级的 —— 已装过的
> 机器再执行同一条安装命令,pip 看到"这个版本已经满足"就不重新下载,
> 用户就永远拿不到后来发布的构建。递增的版本号是这条渠道能被真正
> 升级的前提。

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

`forgemind mcp` 以 stdio 方式提供 12 个 MCP 工具。客户端需要一个**绝对路径**
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

装好之后,一条命令就能看到结果 —— 不需要密钥、不需要配置文件、不需要先
准备数据:

```bash
pip install --extra-index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/ "forgemind[cn]"
forgemind demo
```

`forgemind demo` 会取真实行情、跑一次双均线回测,并把收益、夏普、回撤
与进出次数打印出来。取不到实时行情时,它用包内置的真实历史行情
(600519 在 2024 年的日线,见 `forgemind/data/README.md`),**不会**用随机数
凑一份数据糊弄你。

拿不准某条命令做什么,先看帮助:

```bash
forgemind --help
forgemind backtest --list-strategies   # 有哪些策略
forgemind info                         # 版本、配置与数据源状态
```

也可以写成 Python:

```python
from forgemind.core.backtest.engine import SimpleBacktestEngine
from forgemind.core.data import bundled_sample_path
from forgemind.core.strategies.library import STRATEGY_REGISTRY
import pandas as pd

prices = pd.read_csv(bundled_sample_path(), parse_dates=["date"]).set_index("date")
strategy = STRATEGY_REGISTRY["ma_cross"]()
strategy.validate_parameters()

result = SimpleBacktestEngine(initial_capital=100_000).run(strategy, prices)
print(f"总收益 {result.total_return:+.2%} · 夏普 {result.sharpe:.2f} · 进出 {result.n_trades} 次")
```

常见的几条命令:

```bash
# 取 A 股日线(免费数据源,需要上面的 [cn] 额外依赖)
forgemind etl --symbols 600519,000001 --start 2024-01-01 --end 2024-12-31

# 多因子选股
forgemind pick --symbol 600519.SH --top-n 5

# 回测
forgemind backtest --strategy ma_cross --symbol 600519

# AI 决策(需要配一个模型服务的密钥)
forgemind agent --symbol 600519.SH

# 以 MCP 服务的方式启动,给 Claude Desktop / Cursor 用
forgemind mcp

# 看不同任务会路由到哪个模型服务(只看路由结果,不调模型)
forgemind router-demo
```

装不上、报错、看不懂输出,先看 [FAQ](#-faq) 与[错误码速查表](#-错误码速查表)。

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

**Where it lands locally.** Signals, decisions and backtests are written to a
local DuckDB file — `forgemind info` prints the exact path. The tables are
part of the public surface, so you can query them with any DuckDB client:

| Table | What it holds |
|---|---|
| `signal_history` | every signal that was emitted, with its side, confidence and rationale |
| `kline_daily` | the daily bars pulled by `forgemind etl` (symbol, date, OHLCV) |
| `stock_list` | the symbols `forgemind etl` has seen, with their names |
| `backtest_run` | one row per backtest, with the metrics it produced |
| `portfolio_decision` | the per-agent votes behind a decision |
| `portfolio_snapshot` | the portfolio as it stood at a given moment |
| `portfolio_position` | the positions inside a snapshot |

```python
import pathlib

import duckdb

# 第一次跑的时候这个目录还不存在 —— 建出来,不然 DuckDB 开不了文件。
pathlib.Path("data/duckdb").mkdir(parents=True, exist_ok=True)
con = duckdb.connect("data/duckdb/main.db")
try:
    print(con.execute(
        "SELECT symbol, side, confidence FROM signal_history ORDER BY emitted_at DESC LIMIT 5"
    ).df())
except duckdb.Error:
    # 还没发过信号 —— 说清怎么办,而不是抛一堆栈
    print("还没有信号 —— 先跑:forgemind signal --symbol 600519")
con.close()
```

> Open the file read-write, as above: DuckDB does not let a read-only
> connection and a read-write one open the same file, and ForgeMind holds
> the read-write side.

---

## ❓ FAQ

<details>
<summary><b>Q: 安装时报 "No matching distribution found" 怎么办?</b></summary>

A: 检查你用的是 `--extra-index-url` 不是 `--index-url`:

```bash
# ✅ 正确 — 默认源 (PyPI) 仍可用,只有 forgemind 走我们的索引
pip install --extra-index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/ forgemind

# ❌ 错误 — 会替换默认源,fastapi / duckdb 也去我们的索引里找 → 全部失败
pip install --index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/ forgemind  # 错误示范(故意写错,别照抄)
```

URL 路径是 `/pypi/simple/`,**不要**再加 `/forgemind/`。
</details>

<details>
<summary><b>Q: 桌面端启动报 "Python sidecar 未运行" 怎么办?</b></summary>

A: 桌面端 (Tauri) spawn Python sidecar (forgemind.api.main),需要:
1. 系统已装 Python 3.11+
2. 已 `pip install forgemind` (不是只装桌面端安装包)
3. PATH 里能找到 `forgemind` 命令

验证: 终端跑 `forgemind info` 应输出版本号和 DuckDB 路径。
</details>

<details>
<summary><b>Q: ETL 拉到 0 条数据 / 标的取不到怎么办?</b></summary>

A: 检查:

```bash
# 1. 标的代码格式: 6 位纯数字 (600519),不要带 .SH/.SZ
forgemind etl --symbols 600519,000001 --start 2024-01-01 --end 2024-12-31

# 2. 日期范围不能太短 (建议至少 1 年才有 IC 统计意义)

# 3. 网络可达: akshare 走东方财富 / 腾讯 / 新浪,任一可达即可
```

退出码含义见下表。
</details>

<details>
<summary><b>Q: `forgemind backtest` 报 "在库里没有 K 线" 怎么办?</b></summary>

A: 先跑 ETL 把标的 K 线拉下来:

```bash
forgemind etl --symbols 600519 --start 2022-01-01 --end 2024-12-31
forgemind backtest --symbol 600519 --start 2024-01-01 --end 2024-12-31
```

`forgemind backtest` 默认 DuckDB 真数据优先;如果库里没数据,会用模拟数据,并在结果里标 "模拟数据,非真实市场"、说明这不是真实回测结果。
</details>

<details>
<summary><b>Q: US 股票数据 / 因子怎么没出来?</b></summary>

A: README "Free Data" 列了 US,但实际上 US 数据源全部需要 token (无免费不限流源):

```bash
export FORGEMIND_US_TOKEN=your_alpha_vantage_or_polygon_key
forgemind etl --symbols AAPL --start 2024-01-01 --end 2024-12-31
```

没 token 跑会得到 "未配置 FORGEMIND_US_TOKEN。" 错误。`forgemind info` 显示当前 US 数据源状态。
</details>

<details>
<summary><b>Q: 桌面端开着的时候,终端里的命令报 "本地库正被另一个进程占用" 怎么办?</b></summary>

A: 这是 DuckDB 的文件锁:同一个库文件,同一时间只能一个进程打开(只读模式
也不行 —— 实测过)。桌面端的 sidecar 开着时它就占着那个库,终端里的命令
自然连不上。三条路,挑一条:

```bash
# 1) 关掉桌面端,终端里再跑
# 2) 给桌面端换个数据目录(它自己也就用那个目录)
# 3) 给终端命令换个数据目录
FORGEMIND_DATA_DIR=./data-cli forgemind pick --symbol 600519
```

命令不会假装成功:它会明说"读不到",降级到模拟行情时也会标出来是模拟
数据 —— 你不会拿到一份看着像真实回测的假结果。
</details>

<details>
<summary><b>Q: 多个 test 一起跑就报 "Unique file handle conflict",分开跑又没事?</b></summary>

A: 这是 DuckDB 的已知限制:同一个数据文件不能同时被一个只读连接和一个读写连接打开。
ForgeMind 自己用的就是读写连接,所以正常用不会遇到。你自己写测试时,打开
数据库用读写方式就行:

```python
import pathlib

import duckdb

pathlib.Path("data").mkdir(exist_ok=True)
con = duckdb.connect("data/forgemind.duckdb")  # 不要加 read_only=True
con.close()
```
</details>


## 🛑 错误码速查表

| 退出码 | 类别 | 触发场景 | 建议动作 |
|---|---|---|---|
| 0 | 成功 | 正常完成 | - |
| 1 | 一般错误 | PM 节点已经跑过、仍按审批规则拒绝落盘 | 检查状态再重跑 |
| 2 | 参数与审批类 | argparse 用法错误、没给子命令、策略名不存在、这个命令喂不了该策略、策略要额外参数、演示数据缺列、非交互模式未传 `--yes`;一次装不下(`MemoryError`)也归这里 | 照提示改参数,或缩小标的范围分批跑 |
| 3 | 数据/上游类 | `TimeoutError`(上游无响应)/ 0 bars(取数失败) | 重试或换源 |
| 4 | 资源类 | `OSError errno=28`(磁盘 ENOSPC) | 清理磁盘 |
| 130 | 用户中断 | 按了 Ctrl+C | 重跑 |

举例:
```bash
$ forgemind etl --symbols 600519 --start 2024-01-01 --end 2024-12-31
# 上游 timeout
# 退出码: 3
# 重试: forgemind etl --symbols 600519 --start 2024-01-01 --end 2024-12-31

$ forgemind agent --symbol 600519.SH
# 等待人工审批
# 退出码: 2
# 重试: forgemind agent --symbol 600519.SH --yes  # 跳过审批,真落 snapshot
```

---


## 🧪 Tests

```bash
pytest tests/ -v
# 677 test files · 10412 tests

# 常规档位:真实业务用例,起真实子进程与真实数据库
pytest tests/ -m "not heavy"
# 8572 cases

# 重并发档位:百万级真实运算,单独用更宽的超时执行
pytest tests/ -m heavy
# 1840 cases
```

上面四个数字由流水线每次实跑核对,对不上就红。

重并发档的规模就是设计意图,流水线上的机器跑不完全部用例,这一档在
流水线上按文件分组抽样执行,每个文件仍有代表被执行,代码路径不漏;
规模本身由本地与专用环境验证。

流水线上的实跑结果以 Actions 页面上的运行记录为准 —— 每一轮运行都钉在
它自己的源码提交上。数字会随代码变,写进 README 只会变成一句过期的话。

## 🧪 Verify Your Install

装完之后先确认包本身可用:

```bash
forgemind info                      # 版本、配置与数据源状态
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
| 代码质量与安全 | 代码风格、拼写、依赖漏洞扫描 | `ci-lint.yml` / `ci-security.yml` |
| 源码上的全量测试 | 常规档与重并发档,真实起子进程与真实数据库 | `ci-tests.yml` / `ci-tests.yml` |
| 界面 | Next.js 组件测试与界面数据来源核对 | `ci-ui.yml` / `ci-ui.yml` |
| 重并发完整规模 | 关掉按文件分组抽样，把重并发档的全部用例完整跑一遍 | `ci-heavy-full.yml` / 重并发测试 (完整规模) |
| 装出来的构件 | 下载发布出去的那一个 wheel,装进干净环境,把全量测试跑在上面 | `ci-wheel-suite.yml` / 全量测试跑在发布出去的 wheel 上 |

所有检查跑的都是 main 上"即将发布的那一份提交"。两条路径互相独立:
一条在源码树上跑,另一条在**用户真正装到手上的那个 wheel** 上跑 ——
构建配置漏掉一个子包,源码树里那个模块明明在,只有装出来的那个会 import 报错。

重并发档在流水线上按文件分组抽样(每个文件留一个代表),完整规模另有
一个作业专门跑 —— 规模是那批用例的设计意图,抽样只是机器跑不完时的
妥协。

还有一档把全量测试跑在**装出来的 wheel**上:别的作业验的是源码树,
用户装到的是 wheel,这是两句话。装出来再跑,这句话就不用说了 ——
发布出去的依赖区间是不是用得了,也只有这样才验得出来。

桌面端的**源码构建与实跑**在流水线里完成(三个平台都真跑起来了),
但桌面应用**还没有可下载的安装包** —— Tauri 应用启动的是本机的 Python
sidecar,需要先装好 Python 3.11+ 与本包,没有把解释器打进去。上面表里
"桌面端"一行下载并实跑的是三个平台的**独立二进制**
(`forgemind-<版本>-linux` / `forgemind-<版本>-macos` /
`forgemind-<版本>-windows-x64.exe`),
它们在 [Releases](https://github.com/bin1732/forgemind-pypi/releases) 上。
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
