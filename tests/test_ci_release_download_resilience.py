# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""CI 下载发布物必须扛得住"资产正在被替换"的空窗期

真实故障:verify.yml 的 Linux job 报
    downloaded forgemind-linux (9 bytes)
    FAIL: 文件过小(9),很可能拿到的是错误页而不是二进制

那 9 字节就是 "Not Found"。原因是竞态:

  ship.yml 为绕开 GitHub 的"同名上传 422",先删旧资产再上传同名资产;
  verify.yml 正好在那个空窗期下载 → 404。

而 curl 的重试帮不上忙:
  - `--retry` 默认只重试 5xx/超时,**404 不重试**
  - 没有 `--fail` 时,404 的响应体会被当成内容写进文件,
    要到后面的大小检查才暴露

所以两个下载点都要 `--fail` + 显式轮询重试。
"""

import re
from pathlib import Path

import pytest
import pytest

yaml = pytest.importorskip("yaml", reason="需要 pyyaml 才能解析工作流文件")

WF = Path(__file__).resolve().parent.parent.parent / "pubgit" / ".github" / "workflows"
DOWNLOADERS = ["verify.yml", "verify-desktop.yml"]


def _run_steps(name: str) -> list[str]:
    d = yaml.safe_load((WF / name).read_text(encoding="utf-8"))
    out = []
    for job in d.get("jobs", {}).values():
        for s in job.get("steps", []):
            if "releases/download" in (s.get("run") or ""):
                out.append(s["run"])
    return out


class TestReleaseDownloadIsResilient:
    @pytest.mark.parametrize("wf", DOWNLOADERS)
    def test_download_step_exists(self, wf):
        if not (WF / wf).exists():
            pytest.skip(f"{wf} 不在本地(公开仓检出)")
        assert _run_steps(wf), f"{wf} 里没有下载发布物的步骤"

    @pytest.mark.parametrize("wf", DOWNLOADERS)
    def test_curl_has_fail_flag(self, wf):
        """没有 --fail,404 的响应体会被当内容写进文件"""
        if not (WF / wf).exists():
            pytest.skip("无本地副本")
        import re as _re
        for r in _run_steps(wf):
            # 去掉注释行 —— 说明文字里也出现 "curl",会假阳性
            code = _re.sub(r"^\s*#.*$", "", r, flags=_re.M)
            curl_lines = [l for l in code.splitlines()
                          if "curl " in l and "-o " in l]
            assert curl_lines, f"{wf} 里没找到实际的 curl 下载命令"
            import re as _r2
            for line in curl_lines:
                # -f 常与 -sSL 合并写成 -sSLf,所以要查**旗标串**而不是按空格切词
                flags = _r2.search(r"curl\s+(-\w+)", line)
                assert flags and ("f" in flags.group(1) or "--fail" in line), (
                    f"curl 缺 --fail: {line.strip()}")

    @pytest.mark.parametrize("wf", DOWNLOADERS)
    def test_download_is_retried(self, wf):
        """404 在这里是暂时性的,必须有显式重试"""
        if not (WF / wf).exists():
            pytest.skip("无本地副本")
        for r in _run_steps(wf):
            assert re.search(r"for i in ", r), (
                f"{wf} 的下载没有轮询重试 —— 资产被 ship 替换期间必然 404")
            assert re.search(r"sleep \d+", r), "重试之间应当等待"

    @pytest.mark.parametrize("wf", DOWNLOADERS)
    def test_retry_actually_checks_for_404(self, wf):
        """curl --retry 不管 404,不能用它当唯一手段"""
        if not (WF / wf).exists():
            pytest.skip("无本地副本")
        for r in _run_steps(wf):
            if "--retry" in r:
                assert "for i in " in r, (
                    "只靠 curl --retry 不足以覆盖 404,必须自己轮询")


class TestAllWorkflowsStayParseable:
    @pytest.mark.parametrize("wf", sorted(p.name for p in WF.glob("*.yml")))
    def test_yaml_is_valid(self, wf):
        p = WF / wf
        if not p.exists():
            pytest.skip("无本地副本")
        yaml.safe_load(p.read_text(encoding="utf-8"))

    def test_bash_steps_declare_shell(self):
        """Windows runner 上不带 shell: bash 会跑在 sh/cmd 上"""
        script = WF.parent.parent.parent / "src" / "scripts" / "check_workflow_shell.py"
        if not script.exists():
            pytest.skip("检查脚本不在")
        import subprocess

        r = subprocess.run([__import__("sys").executable, str(script)],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stdout + r.stderr
