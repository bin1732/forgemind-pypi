/**
 * KLineChart — TradingView Lightweight Charts v5.2
 * 真集成:K 线图 + 多 pane + 成交量 + 自适应
 */
"use client";
import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type Time,
} from "lightweight-charts";
import { useAppStore } from "@/lib/store";
import { mcpTool } from "@/lib/tauri";
import { cn } from "@/lib/utils";

interface KlineChartProps {
  symbol?: string;
  height?: number;
}

export function KlineChart({ symbol: propSymbol, height = 400 }: KlineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [noData, setNoData] = useState<string | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const currentSymbol = useAppStore((s) => s.currentSymbol);
  const setCurrentSymbol = useAppStore((s) => s.setCurrentSymbol);
  const symbol = propSymbol || currentSymbol;

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      width: containerRef.current.clientWidth,
      height,
      timeScale: {
        borderColor: "#3f3f46",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: "#3f3f46",
      },
      crosshair: {
        mode: 1,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // 拉真实 K 线
    loadKline(symbol).then(({ candles, volumes, message }) => {
      if (message) {
        setNoData(message);
        setLoading(false);
        return;
      }
      setNoData(null);
      candleSeries.setData(candles);
      volumeSeries.setData(volumes);
      chart.timeScale().fitContent();
      // 把最后一个 close / 真数据写到 store,让 portfolio-panel 算真 PnL
      if (candles.length > 0) {
        const lastClose = candles[candles.length - 1].close;
        useAppStore.getState().setCurrentPrice(symbol, lastClose);
      }
      setLoading(false);
    }).catch((e) => {
      setError(String(e));
      setLoading(false);
    });

    // 自适应
    const handleResize = () => {
      if (chartRef.current && containerRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [symbol, height]);

  return (
    <div className="relative w-full rounded-lg border bg-card">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{symbol}</span>
          <span className="text-xs text-muted-foreground">K 线 · 1d(日线)</span>
        </div>
        <div className="flex gap-1">
          {/* 1m / 5m / 15m / 1h 物理上拿不到 —— DuckDB kline_daily 表只存日线
              (forgemind etl 拉的也是日线)。1d 是唯一真有数据的周期。
              注意: JSX 子节点里的双斜杠注释会被当文本渲染出来,这里必须用块注释。 */}
          {[
            { tf: "1m",  enabled: false, why: "数据源仅日线" },
            { tf: "5m",  enabled: false, why: "数据源仅日线" },
            { tf: "15m", enabled: false, why: "数据源仅日线" },
            { tf: "1h",  enabled: false, why: "数据源仅日线" },
            { tf: "1d",  enabled: true,  why: "" },
          ].map(({ tf, enabled, why }) => (
            <button
              key={tf}
              disabled={!enabled}
              title={why || "日线 — 真实 K 线"}
              className={cn(
                "rounded px-2 py-1 text-xs",
                enabled
                  ? "bg-primary text-primary-foreground"
                  : "cursor-not-allowed bg-muted text-muted-foreground opacity-50"
              )}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
      <div
        ref={containerRef}
        className={cn("w-full", loading && "opacity-50")}
        style={{ height }}
      />
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm text-muted-foreground">加载数据...</span>
        </div>
      )}
      {noData && !loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
          <span className="text-sm text-muted-foreground">{noData}</span>
          <span className="text-xs text-muted-foreground">
            需要先运行 forgemind etl 拉取该标的的行情
          </span>
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm text-destructive">{error}</span>
        </div>
      )}
    </div>
  );
}

/**
 * 从后端拉真实 K 线(经 MCP get_kline)。
 *
 * K 线从 get_kline MCP tool 真数据加载
 * 上影线、下影线、成交量柱,看着和真图一模一样,但每个用户看到的都是
 * 从 100 开始的随机数。没有数据时如实显示空态,不拿随机数顶替。
 */
async function loadKline(symbol: string): Promise<{
  candles: CandlestickData[];
  volumes: HistogramData[];
  message?: string;
}> {
  const raw = await mcpTool<Record<string, unknown>>(
    "get_kline", { symbol, limit: 250 },
  );
  // mcpTool 返 JSON-RPC wrapper {result:{content:[{type,text}]}},
  // text 是二次 JSON 字符串,先解一次
  if (!raw) return { candles: [], volumes: [], message: "未连接后端" };
  const inner = (raw as { result?: { content?: Array<{ text?: string }> } })
                  ?.result?.content?.[0]?.text;
  let r: {
    status: string; bars?: { time: number; open: number; high: number;
                              low: number; close: number; volume: number }[];
    message?: string;
  };
  if (inner) {
    try { r = JSON.parse(inner); }
    catch { return { candles: [], volumes: [], message: "MCP 返回非 JSON" }; }
  } else if ((raw as { status?: string }).status) {
    // mock / 测试 直接返扁平对象时兼容
    r = raw as typeof r;
  } else {
    return { candles: [], volumes: [], message: "MCP 返回格式未知" };
  }
  if (r.status !== "ok" || !r.bars?.length) {
    return { candles: [], volumes: [], message: r.message || "暂无该标的的行情数据" };
  }
  return {
    candles: r.bars.map((b) => ({
      time: b.time as Time, open: b.open, high: b.high, low: b.low, close: b.close,
    })),
    volumes: r.bars.map((b) => ({
      time: b.time as Time, value: b.volume,
      color: b.close >= b.open ? "rgba(34,197,94,0.5)" : "rgba(239,68,68,0.5)",
    })),
  };
}
