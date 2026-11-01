# ForgeMind UI

Next.js 15 + shadcn/ui + Tailwind v4 + Lightweight Charts v5.2

## 真跑(你机器上有 node 18+)

```bash
cd forgemind-ui
npm install
npm run dev
# → http://localhost:3000
```

## 组件

- `app/page.tsx` — 主页面(Workspace 三栏布局)
- `components/workspace-layout.tsx` — 拖拽布局
- `components/kline-chart.tsx` — TradingView Lightweight Charts v5.2
- `components/agent-decision-panel.tsx` — LangGraph 决策面板(真接 /api/v1/agent/decide)
- `components/strategy-panel.tsx` — 策略列表
- `components/command-palette.tsx` — Cmd+K 命令面板

## 依赖(已锁版本)

- next 15.0.3
- react 19.0.0
- lightweight-charts 5.2.1
- Tailwind 4.0
- zustand / react-hook-form / zod

## 与 Backend 集成

```typescript
// 默认指向 http://localhost:8000
fetch("http://localhost:8000/api/v1/agent/decide", { ... })
```

生产改用 NEXT_PUBLIC_API_URL 环境变量。

## License

Apache-2.0