/**
 * shadcn/ui 标准 cn 工具 — clsx + tailwind-merge
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number | null | undefined, digits: number = 2): string {
  // 没有数据时显示 "—",不是 0.00%:"0%" 看着像"算出来是零"。
  if (value == null) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatNumber(value: number, digits: number = 2): string {
  return value.toFixed(digits);
}

export function formatCurrency(
  value: number | null | undefined,
  currency: string = "¥",
): string {
  // 同 formatPercent:没有数据时显示 "—"。¥0 看着像"这个组合一分钱没有",
  // 而真实意思常常是"还没有组合快照"。
  if (value == null) return "—";
  return `${currency}${value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
}