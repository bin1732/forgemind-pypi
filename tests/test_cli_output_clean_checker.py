# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""命令行输出体检器:扫的规则要能双向验。

检查器自己抓错了东西,门禁就成了摆设。这里把每条规则各钉一个方向:

- 用户通道(stdout)里出现 SQL、栈回溯、异常类型名、本机路径、原始日志
  JSON → 必须报出来。
- 运维通道(stderr)里出现 SQL、栈回溯、本机路径 → 必须报出来;
  但结构化日志本身不算问题(stderr 本来就是日志通道)。
- 内部表名出现在输出里 → README 里有交代就不报,没有就报。

真跑一遍所有子命令的那部分由流水线里的检查脚本自己负责(它要几分钟),
这里只验规则本身。
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_cli_output_clean as clean  # noqa: E402


class TestStrictScan:
    """用户通道:内部实现一律不许出现"""

    def test_sql_is_reported(self):
        text = "查询失败:SELECT date, open FROM kline_daily WHERE symbol = ?"
        hits = clean._scan(text, clean.COMPILED_STRICT)
        assert any(label == "SQL 片段" for label, _ in hits), hits

    def test_traceback_is_reported(self):
        text = "Traceback (most recent call last):\n  File x.py"
        hits = clean._scan(text, clean.COMPILED_STRICT)
        assert any(label == "Python 栈回溯" for label, _ in hits), hits

    def test_exception_type_is_reported(self):
        text = '查库失败:CatalogException'
        hits = clean._scan(text, clean.COMPILED_STRICT)
        assert any(label == "异常类型名" for label, _ in hits), hits

    def test_local_path_is_reported(self):
        text = "来自 /home/someone/.local/lib/python3.11/site-packages/x.py"
        hits = clean._scan(text, clean.COMPILED_STRICT)
        assert any(label == "本机绝对路径" for label, _ in hits), hits

    def test_raw_log_json_is_reported(self):
        text = '{"event": "duckdb_storage_init", "timestamp": "2026-01-01T00:00:00Z"}'
        hits = clean._scan(text, clean.COMPILED_STRICT)
        assert any(label == "原始日志 JSON" for label, _ in hits), hits

    def test_clean_output_is_not_reported(self):
        text = "ForgeMind 演示 —— 一条命令看到结果\n  总收益 -28.55% · 夏普 -2.19"
        assert clean._scan(text, clean.COMPILED_STRICT) == []


class TestLooseScan:
    """运维通道:结构化日志没问题,SQL 与路径仍然不行"""

    def test_structured_log_is_allowed(self):
        text = '{"event": "akshare_not_installed", "level": "warning"}'
        assert clean._scan(text, clean.COMPILED_LOOSE) == []

    def test_sql_is_still_reported(self):
        text = "LINE 1: SELECT * FROM kline_daily"
        hits = clean._scan(text, clean.COMPILED_LOOSE)
        assert hits, hits

    def test_path_is_still_reported(self):
        text = "/workspace/x/lib/python3.11/site-packages/y.py:17"
        hits = clean._scan(text, clean.COMPILED_LOOSE)
        assert hits, hits


class TestTableNameRule:
    """内部表名可以出现在输出里,但 README 里有交代"""

    def test_documented_table_is_not_reported(self):
        assert clean.check_table_names("信号已落 DuckDB signal_history", "…| `signal_history` |…") == []

    def test_undocumented_table_is_reported(self):
        problems = clean.check_table_names("信号已落 DuckDB signal_history", "README 里没提这张表")
        assert len(problems) == 1, problems
        assert "signal_history" in problems[0]

    def test_no_table_name_is_not_reported(self):
        assert clean.check_table_names("一切正常", "README") == []


class TestRealReadmeDocumentsTheTables:
    """README 里说的表名要真的在 README 里"""

    def test_readme_documents_the_tables_it_mentions(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        for table in clean.TABLE_NAMES:
            if table in readme:
                assert f"`{table}`" in readme, (
                    f"README 提到了 {table},却没把它写成一张表的条目")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
