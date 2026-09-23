# Contributing to ForgeMind

> ForgeMind — AI Agent Forge: Agent / Skill / MCP / LoRA / Workflow / Plugin builder, with quantitative trading as flagship case study.

## 快速上手

```bash
# Clone
git clone https://github.com/bin1732/ForgeMind.git
cd ForgeMind

# 安装依赖
pip install -e ".[dev]"          # Python 包
cd forgemind-ui && npm install && cd ../..  # UI

# 跑测试
pytest tests/ -q -k "not slow"
cd forgemind-ui && npx jest && cd ../..  # UI tests
```

## 开发约定

### Python
- **风格**: `ruff format` + `ruff check --fix`
- **类型**: Pydantic v2 / Python 3.11+ type hints 全部打开
- **测试**: pytest, `pytest-asyncio`, 覆盖率 ≥ 80%
- **命名**: `snake_case` 函数/变量, `PascalCase` 类/类型, 全小写模块名

### TypeScript / React
- **风格**: ESLint + Prettier (Next.js 15 默认)
- **类型**: 禁止 `any`
- **测试**: Jest + React Testing Library

### Rust (Tauri 桌面端)
- `cargo check --all-targets`
- `cargo fmt`
- `cargo clippy -- -D warnings`

### Git 提交规范

```
feat:     新功能
fix:      修复 bug
docs:     文档改动
refactor: 重构 (无功能变化)
test:     测试相关
chore:    构建 / CI / 依赖更新
perf:     性能优化
```

提交示例:
```bash
git commit -m "feat(strategies): add momentum factor ROC_20_20"
git commit -m "fix(backtest): correct slippage calculation for limit orders"
git commit -m "docs(readme): update quick start guide"
```

## 提 PR 流程

1. Fork → `git checkout -b feat/my-feature`
2. 开发 → 测试 → `ruff check --fix && ruff format`
3. 提交 → Push → GitHub 提 PR
4. CI 必须全部通过 (Python tests + UI tests + Lint + Type check)
5. 描述清楚: 改了什么 / 为什么改 / 怎么验证

## 模块贡献指南

### 因子开发 (`forgemind/core/factors/`)
- 继承 `BaseAlphaFactor`
- 实现 `compute(df: pl.LazyFrame) -> pl.LazyFrame`
- 加 IC 测试

### 策略开发 (`forgemind/core/strategies/`)
- 继承 `BaseStrategy`
- 注册到 `STRATEGY_REGISTRY`

### Agent 开发 (`forgemind/core/agents/`)
- 使用 LangGraph `StateGraph`
- 状态用 `TypedDict`,不用 `BaseModel`

### MCP Server (`forgemind/mcp/`)
- 工具注册到 `ForgeMindMCPServer`
- 每个工具必须有文档注释

## 注意事项

- ❌ **不内置券商 SDK** — 框架定位是研究层,执行层交给用户
- ❌ **不内置交易信号跟单** — 只输出 JSON / MCP / Markdown 报告
- ✅ 所有数据源必须是免费/公开的 (AKShare / tushare / yfinance)
- ✅ 0 broker SDK 依赖是核心设计原则,违反的一律拒绝

## License

Apache-2.0. 贡献代码即表示同意按 Apache-2.0 发布。