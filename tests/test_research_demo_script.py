# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""研究示例脚本要真的能用。

这个脚本是 README 上给用户的入口之一,一直没有用例碰过它,于是
两处真问题一直没被发现:

- `--json` 直接崩:numpy 的标量不是 json 能写的类型。
- stdout 里混着日志行:这个选项的用处就是给程序读,下游一解析就报错。

现在这两条都被钉住。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "research_demo.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )


class TestResearchDemo:
    def test_json_output_is_strictly_valid_json(self):
        """--json 要能被严格解析器读 —— NaN 不是合法 JSON"""
        result = _run("--data-source", "mock", "--no-wfo", "--no-mc", "--json")
        assert result.returncode == 0, result.stderr[-800:]
        # 不用 json.loads 的宽松模式:它接受 NaN,严格的下游不认。
        data = json.loads(result.stdout, parse_constant=_reject_constant)
        assert isinstance(data, dict), "JSON 结果应是一个对象"

    def test_stdout_carries_only_the_result(self):
        """stdout 里不能混日志行 —— 这个选项是给程序读的"""
        result = _run("--data-source", "mock", "--no-wfo", "--no-mc", "--json")
        assert result.returncode == 0, result.stderr[-800:]
        # 日志走 stderr:stdout 的第一行就该是 JSON 的开头
        assert result.stdout.lstrip().startswith("{"), (
            f"stdout 开头不是 JSON:\n{result.stdout[:400]}"
        )

    def test_result_declares_its_data_source(self):
        """数据来源要写出来 —— 合成数据不能被当成真实行情"""
        result = _run("--data-source", "mock", "--no-wfo", "--no-mc", "--json")
        assert result.returncode == 0, result.stderr[-800:]
        data = json.loads(result.stdout, parse_constant=_reject_constant)
        assert data["数据"]["来源"] == "mock", "结果里必须写明数据来源"

    def test_result_has_every_section_with_numbers(self):
        """四段结果都要在,数字都要是数 —— 缺一段就等于没跑完"""
        result = _run("--data-source", "mock", "--no-wfo", "--no-mc", "--json")
        assert result.returncode == 0, result.stderr[-800:]
        data = json.loads(result.stdout, parse_constant=_reject_constant)
        for section in ("数据", "因子", "模型", "回测"):
            assert section in data, f"结果缺 {section} 这一段"
        assert data["数据"]["K 线数"] > 0, "没有取到任何行情"
        for key in ("总收益", "夏普", "最大回撤", "交易次数"):
            assert key in data["回测"], f"回测结果缺 {key}"
            assert data["回测"][key] is not None, f"{key} 算不出来"

    def test_empty_symbols_is_refused(self):
        """没给标的要报错,而不是拿着空列表往下跑"""
        result = _run("--symbols", "", "--json")
        assert result.returncode != 0, "没给标的却跑成功了"
        assert "标的" in (result.stdout + result.stderr)


def _reject_constant(name: str):
    raise ValueError(f"结果里有 {name} —— 那不是合法 JSON")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
