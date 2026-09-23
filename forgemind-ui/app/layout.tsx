import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ForgeMind Desktop — GitHub 头部级量化 Agent",
  description: "多 LLM / 多 Agent / MCP / 166 因子 / Walk-Forward 回测 / Tauri 桌面端",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="antialiased">{children}</body>
    </html>
  );
}