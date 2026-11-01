# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""桌面端证据采集脚本的替身必须与真实现对得上

`scripts/capture_desktop_evidence.py` 采集桌面端界面截图时,要注入一层
Tauri IPC 替身把 invoke 转发到真后端。替身只替"进程间通信"这一层:
命令清单、端点地址、请求体字段、状态字段全部从
`src-tauri/src/lib.rs` 的原码里抽出来。

手抄一份就会跟真实现分家 —— 截图看着对、真机却不是那么回事。这个
测试把替身与真实现钉在一起:

  * Rust 声明的每个命令,替身都得实现(少一个不会崩,但某块数据永远
    空着,截图看着正常,实际没验证到任何东西)
  * 替身给的端点地址必须与 Rust 里写的一字不差
  * 状态对象的字段必须与 Rust 写的完全一致
  * Rust 加了命令而替身没跟上 → 这里红
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import capture_desktop_evidence as cap  # noqa: E402
from check_version_consistency import pyproject_version  # noqa: E402


@pytest.fixture(scope="module")
def contract() -> dict:
    return cap.parse_rust()


@pytest.fixture(scope="module")
def shim(contract: dict) -> str:
    return cap.build_shim(contract, *cap.cargo_versions())


class TestShimMatchesRust:
    def test_every_rust_command_is_implemented(self, contract: dict, shim: str):
        implemented = set(re.findall(r"^  (\w+): async", shim, re.M))
        declared = set(contract["commands"])
        missing = declared - implemented
        assert not missing, f"替身没实现这些命令: {sorted(missing)}"

    def test_endpoints_come_from_the_rust_source(self, contract: dict, shim: str):
        """替身里出现的端点必须都在 Rust 源码里出现过"""
        rust_urls = set(re.findall(r'"(http://[0-9.]+:\d+/[^"]+)"', (REPO / "forgemind-ui" / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")))
        shim_urls = set(re.findall(r'"(http://[0-9.]+:\d+/[^"]+)"', shim))
        assert shim_urls, "替身里一个端点都没有"
        assert shim_urls <= rust_urls, f"替身用了 Rust 里没有的端点: {sorted(shim_urls - rust_urls)}"

    def test_status_fields_match_the_rust(self, contract: dict, shim: str):
        """替身返回的状态字段必须与 Rust 写的完全一致"""
        injected = re.search(r'"statusKeys": \[([^\]]*)\]', shim)
        assert injected, "替身没有注入状态字段清单"
        shim_keys = set(re.findall(r'"(\w+)"', injected.group(1)))
        assert shim_keys == set(contract["status_keys"]), (
            f"状态字段对不上: 替身 {sorted(shim_keys)} / Rust {sorted(contract['status_keys'])}")

    def test_shim_checks_its_own_status_fields(self, shim: str):
        """替身自己也要核对字段 —— 少一个字段时当场报错,而不是安静地少一块数据"""
        assert "状态字段与 Rust 不一致" in shim

    def test_missing_arguments_fail_loudly(self, shim: str):
        """缺参数要报错,不能偷偷补一个 null 上去

        Tauri v2 缺参数时命令根本不执行;替身要是补个 null,后端收到的
        东西与真桌面端就不是一回事了(arguments 收到 null 会被判 422)。
        """
        assert "invalid args" in shim


class TestContractExtraction:
    def test_backend_address_is_the_sidecar_port(self, contract: dict):
        assert contract["base"] == "http://127.0.0.1:8008"

    def test_event_name(self, contract: dict):
        assert contract["event"] == "python-sidecar-ready"

    def test_cargo_versions_are_the_declared_ones(self):
        app_version, tauri_version = cap.cargo_versions()
        assert app_version == pyproject_version(REPO), "桌面端版本要与 pyproject 一致"
        assert tauri_version, "读不到 Tauri 版本"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
