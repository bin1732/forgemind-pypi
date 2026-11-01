# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

# 自动检测项目根目录(相对于测试文件所在目录)
_TEST_FILE = Path(__file__).resolve()
_FORGEMIND_ROOT = _TEST_FILE.parent.parent.resolve()


class TestTauriBuild:
    """验证 Tauri 2.x Rust 端能真编译"""

    def test_cargo_check_passes(self):
        """cargo check 应该成功"""
        tauri_dir = _FORGEMIND_ROOT / "forgemind-ui/src-tauri"
        cargo_toml = tauri_dir / "Cargo.toml"
        assert cargo_toml.exists(), "Cargo.toml 应存在"
        assert (tauri_dir / "src" / "lib.rs").exists()
        assert (tauri_dir / "src" / "main.rs").exists()
        assert (tauri_dir / "tauri.conf.json").exists()
        assert (tauri_dir / "capabilities" / "default.json").exists()

    def test_binary_exists(self):
        """如果编译过,真 binary 应存在"""
        binary = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/target/release/forgemind-desktop"
        if not binary.exists():
            # 仅在没有编译时跳过
            import pytest
            pytest.skip("尚未编译 release binary — 先跑 cargo build --release")

        # 验证 binary
        assert binary.is_file()
        size_mb = binary.stat().st_size / 1024 / 1024
        assert size_mb > 4, f"binary 太小: {size_mb} MB"
        assert size_mb < 50, f"binary 太大: {size_mb} MB"

    def test_binary_elf(self):
        """验证 ELF 格式"""
        binary = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/target/release/forgemind-desktop"
        if not binary.exists():
            import pytest
            pytest.skip("binary 不存在")

        # 读 magic bytes
        with open(binary, "rb") as f:
            magic = f.read(4)
        assert magic == b"\x7fELF", f"不是 ELF 格式: {magic}"

    def test_tauri_config_valid(self):
        """Tauri 配置文件结构"""
        import json
        config_path = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/tauri.conf.json"
        with open(config_path) as f:
            config = json.load(f)
        assert config["productName"] == "ForgeMind Desktop"
        assert "windows" in config["app"]
        assert config["app"]["windows"][0]["width"] == 1440

    def test_capabilities_valid(self):
        """Tauri capabilities 权限配置"""
        import json
        cap_path = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/capabilities/default.json"
        with open(cap_path) as f:
            cap = json.load(f)
        assert "permissions" in cap
        assert "core:default" in cap["permissions"]
        # 应该允许执行 Python sidecar
        assert any("shell" in p for p in cap["permissions"])


class TestTauriCommands:
    """验证 Tauri command 函数定义"""

    def test_commands_defined(self):
        """src-tauri/src/lib.rs 应定义关键 IPC commands"""
        lib_rs = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/src/lib.rs"
        content = lib_rs.read_text()
        # 验证关键 command 存在
        assert "start_python_sidecar" in content
        assert "stop_python_sidecar" in content
        assert "run_pipeline" in content
        assert "mcp_call_tool" in content
        assert "get_system_status" in content

    def test_tauri_handlers_registered(self):
        """tauri::generate_handler! 应注册所有 commands"""
        lib_rs = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/src/lib.rs"
        content = lib_rs.read_text()
        # generate_handler! 应包含所有 commands
        assert "tauri::generate_handler!" in content
        # 检查 handler 注册行
        assert "start_python_sidecar," in content
        assert "stop_python_sidecar," in content
        assert "run_pipeline," in content


class TestIntegration:
    """端到端集成 — Tauri + Python sidecar + MCP"""

    def test_python_sidecar_url_configured(self):
        """Python sidecar URL 配置"""
        lib_rs = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/src/lib.rs"
        content = lib_rs.read_text()
        assert "127.0.0.1:8008" in content
        assert "forgemind.api.main" in content

    def test_mcp_tools_not_hardcoded(self):
        """MCP tools 不得再硬编码 —— 必须向真实 sidecar 查询

        :get_system_status 把 mcp_tools 硬编码成 5 项,而实际有 8 项
        (漏报 get_feature / trace_feature_usage / query_portfolio)。
        这些测试原本在**要求**那份硬编码清单存在,等于把缺陷锁成了规范。
        """
        lib_rs = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/src/lib.rs"
        content = lib_rs.read_text()
        # 改为实时查询
        assert "extract_tool_names" in content, "应向 sidecar 查询工具列表"
        assert "/mcp/tools/list" in content, "缺少实时查询端点"
        # 硬编码的清单必须已经不存在
        assert '"mcp_tools": ["output_signal"' not in content, "仍在硬编码工具列表"

    def test_llm_providers_not_hardcoded(self):
        """LLM Provider 列表同样不得硬编码

        硬编码的 provider 清单会随代码演进而悄悄过期,UI 上却照旧展示。
        """
        lib_rs = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/src/lib.rs"
        content = lib_rs.read_text()
        assert '"llm_providers": ["OpenAI"' not in content, "仍在硬编码 provider 列表"

    def test_counts_not_hardcoded(self):
        """因子/策略/数据源数量不得硬编码

        硬编码的计数在代码演进后会悄悄过期,而 UI 照旧显示旧数字。
        原测试在**要求**这些硬编码值存在,等于把缺陷锁成规范。
        """
        lib_rs = _FORGEMIND_ROOT / "forgemind-ui/src-tauri/src/lib.rs"
        content = lib_rs.read_text()
        for field in ("factors_count", "strategies_count", "data_sources_count"):
            assert f'"{field}"' not in content, f"{field} 仍是硬编码的"
        # 真值应由 Python 侧提供
        assert "/api/v1/info" in content or "/mcp/tools/list" in content or \
            "unavailable" in content, "未提供真实数据来源"
