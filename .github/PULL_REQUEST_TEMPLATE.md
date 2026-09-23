## PR 类型

<!-- 选一个标签 -->
- [ ] 🐛 Bug 修复
- [ ] ✨ 新功能
- [ ] 📖 文档
- [ ] ♻️ 重构
- [ ] ✅ 测试
- [ ] 🔧 CI / DevOps
- [ ] 🧪 性能

## 改了什么 (必填)

> 1-3 句话说清楚

## 为什么改 (必填)

> 这个 PR 解决什么问题?

## 怎么验证 (必填)

> 怎么证明这个 PR 正确? 跑了什么测试?

```bash
# 在这里贴测试命令和结果
pytest tests/ -q -k "test_name"
```

## 影响范围

> 哪些模块/文件改了? 需要通知谁review?

- [ ] `forgemind/core/factors/` — 因子库
- [ ] `forgemind/core/strategies/` — 策略
- [ ] `forgemind/core/agents/` — Agent
- [ ] `forgemind/core/ai/` — AI / Router
- [ ] `forgemind/core/backtest/` — 回测引擎
- [ ] `forgemind/core/pipeline/` — Pipeline
- [ ] `forgemind/mcp/` — MCP Server
- [ ] `forgemind-ui/` — UI 桌面端
- [ ] `tests/` — 测试
- [ ] `docs/` — 文档

## 截图 / 截图 (如有 UI 改动)

<!-- 贴 before/after 对比 -->

## Checklist

- [ ] CI 全部通过 (Python + UI + Lint + Type check)
- [ ] 覆盖率没有下降
- [ ] 新功能有测试
- [ ] `ruff check --fix && ruff format` 已运行
- [ ] commit message 符合规范

---

**Reviewer**: @bin1732