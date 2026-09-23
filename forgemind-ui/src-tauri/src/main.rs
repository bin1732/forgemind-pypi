// ForgeMind Desktop — Tauri 2.x 主入口
// 与 Claude Desktop 同款架构: Rust 后端 + Python sidecar + Next.js 前端

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    forgemind_desktop_lib::run();
}