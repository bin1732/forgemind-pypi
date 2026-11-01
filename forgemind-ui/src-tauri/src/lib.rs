// ForgeMind Desktop — Tauri 2.x 核心逻辑
// - 启动 Python sidecar (FastAPI + 量化 Agent)
// - 集成 MCP 客户端(连接本地 MCP Server)
// - IPC 命令处理
// - 状态管理

use serde::{Deserialize, Serialize};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{Emitter, Manager, State};

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

/// 从 MCP tools/list 响应里提取工具名(纯函数,便于单测)
pub fn extract_tool_names(body: &serde_json::Value) -> Vec<String> {
    body.get("result")
        .and_then(|r| r.get("tools"))
        .and_then(|t| t.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|t| t.get("name").and_then(|n| n.as_str()))
                .map(|s| s.to_string())
                .collect()
        })
        .unwrap_or_default()
}

/// 选解释器:Windows 上通常是 python 而非 python3
pub fn interpreter() -> &'static str {
    if cfg!(windows) { "python" } else { "python3" }
}

/// 校验一次取数响应的形状,返回其中的 tools 数组
pub fn validate_tools_payload(body: &serde_json::Value) -> Result<Vec<String>, String> {
    if let Some(err) = body.get("error") {
        return Err(format!("MCP error: {err}"));
    }
    if body.get("result").is_none() {
        return Err("响应缺少 result 字段".into());
    }
    Ok(extract_tool_names(body))
}

/// sidecar 的健康检查地址
pub const SIDECAR_HEALTH_URL: &str = "http://127.0.0.1:8008/health";

/// 探一次健康端点,通不通就返回通不通。
///
/// 抽成独立函数有两个原因:
///   1. 能用真 TCP 边界单独验证(不必起 sidecar 进程)
///   2. 它是本文件里唯一跨 await 碰网络的片段,单独存在时更容易看出
///      「await 期间不持有 std 锁」这条约束
async fn probe_health(client: &reqwest::Client, url: &str) -> bool {
    client.get(url).send().await.is_ok()
}

/// sidecar 的数据目录 —— 用户自己的应用数据目录。
///
/// 拿不到时退回当前目录下的 data/:那至少是可写的(开发环境就是这样),
/// 总比把库塞进只读的安装目录强。
fn sidecar_data_dir(app_data_dir: Option<&std::path::Path>) -> String {
    match app_data_dir {
        Some(dir) => dir.to_string_lossy().to_string(),
        None => "./data".to_string(),
    }
}

/// 启动 Python sidecar 并等它真的能应答,返回就绪的子进程。
///
/// 锁的用法:整个函数**不持有** python_sidecar 的锁。
/// std::sync::MutexGuard 不是 Send,一旦跨 await 存活,调用方
/// (tauri command)的 future 就不再是 Send,tauri 编译会直接报
/// "future cannot be sent between threads safely"。所以锁只在
/// 调用方需要读写 child 的瞬间持有,一次都不跨 await。
async fn spawn_and_wait_for_sidecar(
    py: &str,
    health_url: &str,
    data_dir: &str,
) -> Result<Child, String> {
    // 选解释器:Windows 上通常是 python 而非 python3,直接写死 python3
    // 会让 sidecar 永远起不来,但下面只按 spawn 成功就报"已启动"。
    let mut child = Command::new(py)
        .args(&[
            "-m", "forgemind.api.main",
            "--host", "127.0.0.1",
            "--port", "8008",
        ])
        .env("FORGEMIND_API_SECRET_KEY", "a".repeat(32))
        // 数据目录必须指到用户自己的地方。
        //
        // Python 侧的数据路径是相对当前目录的("./data"),而 sidecar 继承的是
        // 桌面端的当前目录 —— 装完之后那可能是只读的安装目录或根目录,
        // 于是 DuckDB 建不出来、决策日志也写不进去,面板读到的永远是空库。
        // 这里显式给它一个可写的用户目录。
        .env("FORGEMIND_DATA_DIR", data_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start Python sidecar with `{}`: {}", py, e))?;

    // 确认它真的能服务:spawn 成功 ≠ 进程跑得起来(缺依赖、端口占用都会秒退),
    // 进程还活着 ≠ 已经能应答 —— Python 要一两秒才导入完依赖、才监听端口。
    // 之前这里只等 300 毫秒就报"已启动",前端紧接着发请求必然连不上,
    // 界面上显示成"后端连不上",而实际上后端只是还在启动。
    // 轮询健康端点,等它真的应答为止。
    let client = reqwest::Client::new();
    let mut ready = false;
    for _ in 0..120 {
        match child.try_wait() {
            Ok(Some(status)) => {
                return Err(format!(
                    "Python sidecar 启动后退出 (status={});请检查 `{} -m forgemind.api.main` 是否可用",
                    status, py
                ));
            }
            Ok(None) => {}
            Err(e) => return Err(format!("无法确认 sidecar 状态: {}", e)),
        }
        if probe_health(&client, health_url).await {
            ready = true;
            break;
        }
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    }
    if !ready {
        return Err(format!(
            "Python sidecar 起来了但 {} 一直不应答;请确认它没有卡在导入依赖上",
            health_url
        ));
    }
    Ok(child)
}

/// 启动 Python sidecar (FastAPI on localhost:8008)
#[tauri::command]
async fn start_python_sidecar(app: tauri::AppHandle, state: State<'_, AppState>) -> Result<String, String> {
    // 第一次拿锁:只确认当前没有 sidecar 在跑,立刻把锁放掉。
    {
        let guard = state.python_sidecar.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            return Ok("Python sidecar already running".to_string());
        }
    }

    // 这一段没有锁,全是 await —— 见 spawn_and_wait_for_sidecar 的说明。
    // 用**本地**数据目录,不用漫游目录:漫游目录(如 Windows 的 %APPDATA%)
    // 会把 DuckDB 文件跟着同步走 —— 数据库文件被同步进程锁住、两边改同一个
    // 文件,迟早出问题。本地数据目录才是数据库该待的地方。
    let data_dir = sidecar_data_dir(app.path().app_local_data_dir().ok().as_deref());
    let mut child = spawn_and_wait_for_sidecar(interpreter(), SIDECAR_HEALTH_URL, &data_dir).await?;

    // 第二次拿锁:把 child 存进去。
    {
        let mut guard = state.python_sidecar.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            // 等 sidecar 就绪这段时间里,别的调用已经启了一个。
            // 自己这份收掉 —— 两个进程抢同一个端口,后起来的那个只会一直报端口占用。
            child.kill().ok();
            child.wait().ok();
            return Ok("Python sidecar already running".to_string());
        }
        *guard = Some(child);
    }

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

/// 读一个 MCP resource(桌面端用)
///
/// 之前只有 mcp_call_tool(tools/call)。resources 在 stdio 上可达,但桌面端
/// 走 HTTP,而 API 侧当时也没有 resources/read 的 HTTP 形态 ——
/// 于是 forgemind://features、forgemind://strategies 对桌面端"存在但够不着",
/// factor-grid / strategy-panel 只能显示硬编码的假数据。
#[tauri::command]
async fn read_mcp_resource(uri: String) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let url = "http://127.0.0.1:8008/mcp/resources/read";

    let response = client
        .post(url)
        .json(&serde_json::json!({ "uri": uri }))
        .send()
        .await
        .map_err(|e| format!("resource read failed: {}", e))?;

    let status = response.status();
    if status == reqwest::StatusCode::NO_CONTENT {
        return Ok(serde_json::json!({"ok": true}));
    }
    if !status.is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(format!("resource read failed ({}): {}", status, body));
    }
    let result: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse resource: {}", e))?;
    if let Some(err) = result.get("error") {
        return Err(format!("MCP error: {}", err));
    }
    Ok(result)
}

/// 获取系统状态
///
/// 工具清单必须向真实 sidecar 查询:固定的清单会漏报新工具
/// (get_feature / trace_feature_usage / query_portfolio),而
/// factors/strategies 的数字也会随代码变化悄悄过期。
/// sidecar 不在时如实报告 unavailable,不再编造。
#[tauri::command]
async fn get_system_status(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let python_sidecar_running = {
        // try_wait 需要 &mut Child,必须先把 Mutex 锁拿成可变借用
        let mut guard = state.python_sidecar.lock().map_err(|e| e.to_string())?;
        match guard.as_mut() {
            Some(c) => c.try_wait().ok().flatten().is_none(),
            None => false,
        }
    };

    let client = reqwest::Client::new();
    // 15 轮 fix: tools/list 协议只返 tools[] 不返 resources[]
    // 必须单独调 /mcp/resources/list 拿 resources
    let tools_url = "http://127.0.0.1:8008/mcp/tools/list";
    let resources_url = "http://127.0.0.1:8008/mcp/resources/list";

    let live = if python_sidecar_running {
        // 并行拉 tools + resources 两个端
        let (tools_resp, resources_resp) = tokio::join!(
            client.get(tools_url).send(),
            client.get(resources_url).send(),
        );
        // tools/list 协议只返 tools[] 不返 resources[],
        // resources 的数量要另外从 /mcp/resources/list 数。
        // 这里只解构 tools 那一路 —— 早先顺手多带了一个 resources_count,
        // 立刻被下面重新算出的同名变量覆盖,编译器会报 unused 警告。
        let (tools_count, tools_names) = match tools_resp {
            Ok(resp) if resp.status().is_success() => {
                let body: serde_json::Value = resp.json().await.unwrap_or_default();
                let tools = extract_tool_names(&body);
                let count = body
                    .get("result")
                    .and_then(|r| r.get("tools"))
                    .and_then(|t| t.as_array())
                    .map(|a| a.len())
                    .unwrap_or(0);
                (count, tools)
            }
            _ => (0, vec![]),
        };
        let resources_count = match resources_resp {
            Ok(resp) if resp.status().is_success() => resp
                .json::<serde_json::Value>()
                .await
                .ok()
                .and_then(|b| b.get("result").and_then(|r| r.get("resources")).and_then(|r| r.as_array()).cloned())
                .map(|a| a.len())
                .unwrap_or(0),
            _ => 0,
        };
        Some(serde_json::json!({
            "mcp_tools": tools_names,
            "mcp_tool_count": tools_count,
            "mcp_resource_count": resources_count,
        }))
    } else {
        None
    };

    let mut out = serde_json::json!({
        "app_version": env!("CARGO_PKG_VERSION"),
        "tauri_version": tauri::VERSION,
        "python_sidecar_running": python_sidecar_running,
    });

    match live {
        Some(l) => {
            // 真实数据。sidecar 回来的应当是对象 —— 万一不是,不能 panic
            // 把整个桌面端带下去,按能拿到的字段如实给出。
            match l.as_object() {
                Some(fields) => {
                    for (k, v) in fields {
                        out[k] = v.clone();
                    }
                }
                None => {
                    out["mcp_tools"] = serde_json::Value::Null;
                    out["mcp_tool_count"] = serde_json::Value::Null;
                    out["status_note"] = serde_json::json!(
                        "Python sidecar 返回的不是对象,拿不到真实能力清单"
                    );
                }
            }
        }
        None => {
            // sidecar 未运行:如实说明拿不到,而不是编造一份
            out["mcp_tools"] = serde_json::Value::Null;
            out["mcp_tool_count"] = serde_json::Value::Null;
            out["status_note"] = serde_json::json!(
                "Python sidecar 未运行,无法获取真实能力清单;请先调用 start_python_sidecar"
            );
        }
    }

    Ok(out)
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
            read_mcp_resource,
            get_system_status,
        ])
        .run(tauri::generate_context!())
        .expect("error while running ForgeMind desktop");
}
// ===== 单元测试 =====
//
// 这些测试覆盖曾被实测抓到的真实缺陷:
//   * get_system_status 曾把 mcp_tools 写死成 5 个而实际有 8 个
//     (漏报 get_feature / trace_feature_usage / query_portfolio)
//   * start_python_sidecar 曾硬编码 "python3",在多数 Windows 上不存在,
//     却只要 spawn 成功就报"已启动"
#[cfg(test)]
mod tests {
    use super::*;

    fn sample_tools_payload(n: usize) -> serde_json::Value {
        let tools: Vec<serde_json::Value> = (0..n)
            .map(|i| serde_json::json!({"name": format!("tool_{i}")}))
            .collect();
        serde_json::json!({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": tools}
        })
    }

    #[test]
    fn extracts_all_tool_names_not_a_hardcoded_five() {
        // 无论 sidecar 返回什么,都返回同一份固定清单
        for n in 1..=12 {
            let body = sample_tools_payload(n);
            assert_eq!(extract_tool_names(&body).len(), n, "提取数与实际不符");
        }
    }

    #[test]
    fn extraction_is_stable_across_calls() {
        let body = sample_tools_payload(8);
        let a = extract_tool_names(&body);
        let b = extract_tool_names(&body);
        assert_eq!(a, b);
        assert_eq!(a[0], "tool_0");
    }

    #[test]
    fn missing_result_is_reported_not_silently_empty() {
        let body = serde_json::json!({"jsonrpc": "2.0", "id": 1});
        assert!(validate_tools_payload(&body).is_err());
    }

    #[test]
    fn jsonrpc_error_is_surfaced() {
        let body = serde_json::json!({
            "jsonrpc": "2.0", "id": 1,
            "error": {"code": -32601, "message": "Unknown tool"}
        });
        let err = validate_tools_payload(&body).unwrap_err();
        assert!(err.contains("MCP error"), "未透出 JSON-RPC 错误: {err}");
    }

    #[test]
    fn wellformed_payload_validates() {
        let body = sample_tools_payload(8);
        assert!(validate_tools_payload(&body).is_ok());
    }

    #[test]
    fn interpreter_matches_platform() {
        let py = interpreter();
        if cfg!(windows) {
            assert_eq!(py, "python", "Windows 上应用 python,硬编码 python3 会起不来");
        } else {
            assert_eq!(py, "python3");
        }
    }

    // ===== sidecar 就绪判定 =====

    /// 编译期断言:这些 future 必须是 Send。
    ///
    /// tauri 要求 command 的 future 是 Send。之前 start_python_sidecar
    /// 在轮询健康端点的 await 期间一直持着 python_sidecar 的
    /// std::sync::MutexGuard,Guard 不是 Send,于是整个 command 的 future
    /// 失去 Send,tauri 编译直接失败("future cannot be sent between
    /// threads safely")。这里把约束显式写出来:改这两个函数时,
    /// 一旦又有人在 await 期间拿着 std 锁,这个测试就编译不过。
    #[test]
    fn sidecar_futures_are_send() {
        fn assert_send<F: std::future::Future + Send>(_f: F) {}
        let client = reqwest::Client::new();
        assert_send(probe_health(&client, SIDECAR_HEALTH_URL));
        assert_send(spawn_and_wait_for_sidecar(
            "python3",
            SIDECAR_HEALTH_URL,
            "./data",
        ));
    }

    /// sidecar 的数据目录必须落在用户自己的地方
    #[test]
    fn sidecar_data_dir_is_the_app_data_dir() {
        let dir = std::path::Path::new("/home/someone/.local/share/ForgeMind");
        assert_eq!(sidecar_data_dir(Some(dir)), dir.to_string_lossy());
        // 拿不到应用数据目录时退回当前目录下的 data/(至少是可写的)
        assert_eq!(sidecar_data_dir(None), "./data");
    }

    /// 起一个最小 HTTP 服务,探它必须成功 —— 走真 TCP 边界,不是 mock
    #[tokio::test]
    async fn health_probe_reports_a_live_server() {
        use tokio::io::{AsyncReadExt, AsyncWriteExt};

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            let (mut socket, _) = listener.accept().await.unwrap();
            let mut buf = [0u8; 1024];
            let _ = socket.read(&mut buf).await;
            let _ = socket
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                .await;
        });

        let client = reqwest::Client::new();
        assert!(
            probe_health(&client, &format!("http://{addr}/health")).await,
            "真在监听的服务必须探得到"
        );
    }

    /// 探一个没人监听的端口必须失败 —— 探不到就要说探不到,不能当通
    #[tokio::test]
    async fn health_probe_reports_a_dead_port() {
        // 先占一个端口拿到号,再放掉 —— 之后连它必然没人应答
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        drop(listener);

        let client = reqwest::Client::new();
        assert!(
            !probe_health(&client, &format!("http://{addr}/health")).await,
            "没人监听的端口必须探不到"
        );
    }
}
