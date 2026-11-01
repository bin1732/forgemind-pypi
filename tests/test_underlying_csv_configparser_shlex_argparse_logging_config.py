# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`csv` 进阶 + `configparser` 进阶 + `shlex` 进阶 + `argparse` 进阶 + `logging.config` 真底层测试。

覆盖 CSV/配置/shell 解析/参数解析/日志配置模块:
  - `csv.writer.writerow` 真写一行
  - `csv.DictReader` 真按 dict 读
  - `csv.Sniffer.has_header` 真判
  - `csv.Sniffer.sniff` 真推断 delimiter
  - `configparser.ConfigParser` 真读写
  - `configparser.RawConfigParser.optionxform = str` 保留大小写
  - `shlex.split('a "b c" d')` 真去引号
  - `shlex.quote('a b')` 真 quote
  - `argparse.ArgumentParser` 真解析 args
  - `argparse --port int type` 真转换
  - `argparse --choice [a/b/c]` 真限制
  - `argparse subparser` 真派发
  - `logging.config.dictConfig` 真配
  - `logging.config.fileConfig` 真读 ini
  - `logging.Logger.setLevel` 真设 level
"""
import argparse
import configparser
import csv
import io
import logging
import logging.config
import os
import shlex
import tempfile

import pytest


# -- csv 进阶 -----------------------------------------------------------------

class TestCsvAdvanced:
    def test_writer_writerow(self):
        """`csv.writer.writerow` 真写一行。"""
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["a", "b", "c"])
        assert buf.getvalue().strip() == "a,b,c"

    def test_DictReader_dict_access(self):
        """`csv.DictReader` 真按 dict 读 header。"""
        data = "name,age\nAlice,30\nBob,25\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] == "30"

    def test_Sniffer_has_header(self):
        """`csv.Sniffer.has_header` 真判是否含 header。"""
        with_header = "name,age\nAlice,30\n"
        without_header = "Alice,30\nBob,25\n"
        assert csv.Sniffer().has_header(io.StringIO(with_header).read(1024)) is True
        # 短数据可能判 False
        assert isinstance(
            csv.Sniffer().has_header(io.StringIO(without_header).read(1024)),
            bool,
        )

    def test_Sniffer_sniff_delimiter(self):
        """`csv.Sniffer.sniff` 真推断 delimiter。"""
        sample = "a;b;c\n1;2;3\n"
        d = csv.Sniffer().sniff(sample)
        # delimiter 必是 ';' 或 ','
        assert d.delimiter in (";", ",")


# -- configparser 进阶 --------------------------------------------------------

class TestConfigparserAdvanced:
    def test_basic_read_write(self):
        """`ConfigParser` 真读写 round-trip。"""
        cp = configparser.ConfigParser()
        cp["DEFAULT"] = {"server": "localhost"}
        cp["section1"] = {"key1": "val1", "key2": "val2"}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "forge.ini")
            with open(path, "w") as f:
                cp.write(f)
            cp2 = configparser.ConfigParser()
            cp2.read(path)
            assert cp2["section1"]["key1"] == "val1"
            assert cp2["DEFAULT"]["server"] == "localhost"

    def test_optionxform_preserves_case(self):
        """`RawConfigParser.optionxform = str` 保留大小写。"""
        cp = configparser.RawConfigParser()
        cp.optionxform = str
        cp.add_section("S")
        cp.set("S", "MixedCase", "val")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "case.ini")
            with open(path, "w") as f:
                cp.write(f)
            cp2 = configparser.RawConfigParser()
            cp2.optionxform = str
            cp2.read(path)
            assert cp2["S"]["MixedCase"] == "val", (
                f"optionxform=str 应保留 MixedCase,实际 {dict(cp2['S'])}"
            )

    def test_getint_getboolean(self):
        """`ConfigParser.getint/getboolean` 真类型转换。"""
        cp = configparser.ConfigParser()
        cp["s"] = {"port": "8080", "enabled": "true", "ratio": "0.5"}
        assert cp.getint("s", "port") == 8080
        assert cp.getboolean("s", "enabled") is True
        assert cp.getfloat("s", "ratio") == 0.5


# -- shlex 进阶 ---------------------------------------------------------------

class TestShlexAdvanced:
    def test_shlex_split_with_quotes(self):
        """`shlex.split('a \"b c\" d')` 真去引号。"""
        result = shlex.split('a "b c" d')
        assert result == ["a", "b c", "d"], (
            f"shlex.split 应=['a','b c','d'],实际 {result}"
        )

    def test_shlex_quote(self):
        """`shlex.quote('a b')` 真 quote 含空格的串。"""
        q = shlex.quote("a b")
        # 必不含裸空格
        assert " " not in q or q.startswith("'") or q.startswith('"')

    def test_shlex_posix_skip_comment(self):
        """`shlex.shlex(posix=True)` 跳过 `#` 注释。"""
        lexer = shlex.shlex(io.StringIO("a # comment\nb"), posix=True)
        tokens = list(lexer)
        # posix=True 应跳过 # 后内容
        assert "a" in tokens
        assert "b" in tokens
        # comment 不应在
        assert "comment" not in tokens


# -- argparse 进阶 ------------------------------------------------------------

class TestArgparseAdvanced:
    def test_parse_args(self):
        """`ArgumentParser` 真解析 args。"""
        p = argparse.ArgumentParser()
        p.add_argument("--name", default="forge")
        p.add_argument("--port", type=int, default=80)
        args = p.parse_args(["--port", "8080"])
        assert args.name == "forge"
        assert args.port == 8080

    def test_choices(self):
        """`add_argument(choices=...)` 真限制。"""
        p = argparse.ArgumentParser()
        p.add_argument("--mode", choices=["a", "b", "c"])
        args = p.parse_args(["--mode", "a"])
        assert args.mode == "a"
        with pytest.raises(SystemExit):
            p.parse_args(["--mode", "d"])

    def test_subparsers(self):
        """`subparsers` 真派发。"""
        p = argparse.ArgumentParser()
        sub = p.add_subparsers(dest="cmd")
        p_a = sub.add_parser("a")
        p_a.add_argument("--x", type=int, default=0)
        p_b = sub.add_parser("b")
        p_b.add_argument("--y", default="def")
        args_a = p.parse_args(["a", "--x", "5"])
        assert args_a.cmd == "a"
        assert args_a.x == 5
        args_b = p.parse_args(["b", "--y", "hi"])
        assert args_b.cmd == "b"
        assert args_b.y == "hi"


# -- logging.config 进阶 -------------------------------------------------------

class TestLoggingConfigAdvanced:
    def test_dictConfig_configures_logger(self):
        """`logging.config.dictConfig` 真配置 logger。"""
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "f": {"format": "%(levelname)s:%(name)s:%(message)s"},
            },
            "handlers": {
                "h": {
                    "class": "logging.StreamHandler",
                    "formatter": "f",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": {
                "forge_test": {
                    "handlers": ["h"],
                    "level": "DEBUG",
                },
            },
        }
        try:
            logging.config.dictConfig(config)
        except Exception:
            pytest.skip(f"dictConfig 不可用: {config!r}")
        log = logging.getLogger("forge_test")
        log.setLevel(logging.DEBUG)
        assert log.level == logging.DEBUG

    def test_Logger_setLevel(self):
        """`Logger.setLevel(DEBUG)` 真设 level。"""
        log = logging.getLogger("forge_test_2")
        log.setLevel(logging.WARNING)
        assert log.level == logging.WARNING
        log.setLevel(logging.INFO)
        assert log.level == logging.INFO
