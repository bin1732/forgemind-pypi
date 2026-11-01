/**
 * shadcn/ui 标准 cn 工具 — clsx + tailwind-merge
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number, digits: number = 2): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatNumber(value: number, digits: number = 2): string {
  return value.toFixed(digits);
}

export function formatCurrency(value: number, currency: string = "¥"): string {
  return `${currency}${value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
}