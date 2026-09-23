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
import { cn } from "@/lib/utils";

interface KlineChartProps {
  symbol?: string;
  height?: number;
}

export function KlineChart({ symbol: propSymbol, height = 400 }: KlineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
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

    // 加载示例数据(实际应从后端 API 拉)
    loadSampleData(symbol).then(({ candles, volumes }) => {
      candleSeries.setData(candles);
      volumeSeries.setData(volumes);
      chart.timeScale().fitContent();
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
          <span className="text-xs text-muted-foreground">K 线 · 5m</span>
        </div>
        <div className="flex gap-1">
          {["1m", "5m", "15m", "1h", "1d"].map((tf) => (
            <button
              key={tf}
              className="rounded px-2 py-1 text-xs hover:bg-accent"
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
      {error && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm text-destructive">{error}</span>
        </div>
      )}
    </div>
  );
}

async function loadSampleData(symbol: string): Promise<{
  candles: CandlestickData[];
  volumes: HistogramData[];
}> {
  // 真实场景应从 /api/kline?symbol=... 拉
  // 这里返回合成数据用于演示
  const candles: CandlestickData[] = [];
  const volumes: HistogramData[] = [];
  const now = Math.floor(Date.now() / 1000);
  let price = 100;
  
  for (let i = 100; i >= 0; i--) {
    const time = (now - i * 300) as Time;
    const ret = (Math.random() - 0.5) * 0.02;
    const open = price;
    const close = price * (1 + ret);
    const high = Math.max(open, close) * (1 + Math.random() * 0.005);
    const low = Math.min(open, close) * (1 - Math.random() * 0.005);
    candles.push({
      time,
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
    });
    volumes.push({
      time,
      value: Math.floor(Math.random() * 1000000),
      color: close >= open ? "#22c55e50" : "#ef444450",
    });
    price = close;
  }
  
  return { candles, volumes };
}