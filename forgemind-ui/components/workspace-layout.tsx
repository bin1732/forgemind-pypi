/**
 * Workspace 拖拽布局 — 三栏 IDE
 * 对标 OpenBB Workspace / QuantConnect IDE / TradingView
 */
"use client";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface WorkspaceLayoutProps {
  header?: ReactNode;
  left?: ReactNode;
  center: ReactNode;
  right?: ReactNode;
  footer?: ReactNode;
  activeLayout?: string;
}

export function WorkspaceLayout({
  header,
  left,
  center,
  right,
  footer,
  activeLayout = "default",
}: WorkspaceLayoutProps) {
  // 不同的 layout 用不同的栅格
  const layouts: Record<string, string> = {
    default: "grid-cols-[240px_1fr_300px]",
    research: "grid-cols-[300px_1fr_240px]",
    trading: "grid-cols-[200px_1fr_400px]",
  };

  return (
    <div className="grid h-screen grid-rows-[auto_1fr_auto]">
      {header && <div className="border-b bg-card">{header}</div>}
      <div className={cn("grid overflow-hidden", layouts[activeLayout] || layouts.default)}>
        {left && (
          <aside className="border-r bg-card overflow-y-auto">{left}</aside>
        )}
        <section className="overflow-y-auto bg-background">{center}</section>
        {right && (
          <aside className="border-l bg-card overflow-y-auto">{right}</aside>
        )}
      </div>
      {footer && <div className="border-t bg-card">{footer}</div>}
    </div>
  );
}