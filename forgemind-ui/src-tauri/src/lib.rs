// ForgeMind Desktop — Tauri 2.x 核心逻辑
// - 启动 Python sidecar (FastAPI + 量化 Agent)
// - 集成 MCP 客户端(连接本地 MCP Server)
// - IPC 命令处理
// - 状态管理

use serde::{Deserialize, Serialize};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{Emitter, State};

#[derive(Default)]
pub struct AppState {
    pub python_sidecar: Mutex<Option<Child>>,
    pub mcp_client: Mutex<Option<McpClient>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SignalOutput {
    pub symbol: String,
    pub date: String,
    pub direction: String,
    pub confidence: f64,
    pub signal: f64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PipelineResult {
    pub symbols: Vec<String>,
    pub n_symbols: usize,
    pub n_days: usize,
    pub n_bars: usize,
    pub sharpe: f64,
    pub max_drawdown: f64,
    pub signals: Vec<SignalOutput>,
}

/// 启动 Python sidecar (FastAPI on localhost:8008)
#[tauri::command]
async fn start_python_sidecar(app: tauri::AppHandle, state: State<'_, AppState>) -> Result<String, String> {
    let mut guard = state.python_sidecar.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok("Python sidecar already running".to_string());
    }

    // 启动 Python sidecar
    let child = Command::new("python3")
        .args(&[
            "-m", "forgemind.api.main",
            "--host", "127.0.0.1",
            "--port", "8008",
        ])
        .env("FORGEMIND_API_SECRET_KEY", "a".repeat(32))
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start Python sidecar: {}", e))?;

    *guard = Some(child);

    // 通知前端 sidecar 已就绪
    app.emit("python-sidecar-ready", ()).ok();

    Ok("Python sidecar started on http://127.0.0.1:8008".to_string())
}

/// 停止 Python sidecar
#[tauri::command]
async fn stop_python_sidecar(state: State<'_, AppState>) -> Result<String, String> {
    let mut guard = state.python_sidecar.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = guard.take() {
        child.kill().ok();
        child.wait().ok();
        Ok("Python sidecar stopped".to_string())
    } else {
        Ok("Python sidecar not running".to_string())
    }
}

/// 调用 Python sidecar 跑流水线
#[tauri::command]
async fn run_pipeline(symbols: Vec<String>, start: String, end: String) -> Result<PipelineResult, String> {
    let client = reqwest::Client::new();
    let url = "http://127.0.0.1:8008/api/pipeline/run";

    let body = serde_json::json!({
        "symbols": symbols,
        "start": start,
        "end": end,
    });

    let response = client
        .post(url)
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Pipeline request failed: {}", e))?;

    let result: PipelineResult = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse pipeline result: {}", e))?;

    Ok(result)
}

/// 调用 MCP 工具 (output_signal / stock_pick 等)
#[tauri::command]
async fn mcp_call_tool(tool_name: String, arguments: serde_json::Value) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let url = "http://127.0.0.1:8008/mcp/tools/call";

    let response = client
        .post(url)
        .json(&serde_json::json!({
            "name": tool_name,
            "arguments": arguments,
        }))
        .send()
        .await
        .map_err(|e| format!("MCP call failed: {}", e))?;

    let status = response.status();
    if !status.is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(format!("MCP call failed ({}): {}", status, body));
    }

    // 204 No Content (notifications/initialized) → 空响应
    if status == reqwest::StatusCode::NO_CONTENT {
        return Ok(serde_json::json!({"ok": true}));
    }

    let result: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse MCP result: {}", e))?;

    // JSON-RPC error → 转成 Rust error
    if let Some(err) = result.get("error") {
        return Err(format!("MCP error: {}", err));
    }

    Ok(result)
}

/// 获取系统状态 (OTel metrics)
#[tauri::command]
async fn get_system_status(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "app_version": env!("CARGO_PKG_VERSION"),
        "tauri_version": tauri::VERSION,
        "python_sidecar_running": state.python_sidecar.lock().map_err(|e| e.to_string())?.is_some(),
        "mcp_tools": ["output_signal", "stock_pick", "run_backtest", "search_features", "check_ic_decay"],
        "llm_providers": ["OpenAI", "Anthropic", "Qwen", "DeepSeek", "Gemini", "Mistral", "Ollama", "vLLM", "LM Studio"],
        "factors_count": 166,
        "strategies_count": 17,
        "data_sources_count": 6,
    }))
}

// ===== MCP Client =====
pub struct McpClient {
    pub endpoint: String,
}

impl McpClient {
    pub fn new(endpoint: String) -> Self {
        Self { endpoint }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            start_python_sidecar,
            stop_python_sidecar,
            run_pipeline,
            mcp_call_tool,
            get_system_status,
        ])
        .run(tauri::generate_context!())
        .expect("error while running ForgeMind desktop");
}