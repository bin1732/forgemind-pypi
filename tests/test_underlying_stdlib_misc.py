# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 stdlib misc — logging 真流到 file / argparse 真解析 / configparser 真读 INI / decimal 真精度。
"""
import argparse
import configparser
import decimal
import io
import logging
import os
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

import pytest


def test_logging_real_appends_to_file(tmp_path):
    """logging 真配 FileHandler + 真写 log 到磁盘"""
    log_file = tmp_path / "test.log"
    logger = logging.getLogger("test_logger_real")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(str(log_file))
    handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
    logger.addHandler(handler)

    logger.info("hello info")
    logger.warning("hello warning")
    logger.error("hello error")
    handler.flush()
    handler.close()

    content = log_file.read_text()
    assert "INFO:hello info" in content
    assert "WARNING:hello warning" in content
    assert "ERROR:hello error" in content


def test_logging_real_levels_filter(tmp_path):
    """logging 真按 level 过滤 (DEBUG 被 INFO 拦)"""
    log_file = tmp_path / "level.log"
    logger = logging.getLogger("test_logger_level")
    logger.setLevel(logging.WARNING)
    # 删之前的 handler
    logger.handlers = []
    handler = logging.FileHandler(str(log_file))
    logger.addHandler(handler)

    logger.debug("debug_msg")  # 不应写
    logger.info("info_msg")  # 不应写
    logger.warning("warning_msg")  # 应写
    logger.error("error_msg")  # 应写
    handler.flush()
    handler.close()

    content = log_file.read_text()
    assert "debug_msg" not in content
    assert "info_msg" not in content
    assert "warning_msg" in content
    assert "error_msg" in content


def test_logging_real_capture_warnings(tmp_path):
    """logging.captureWarnings 真把 Python warning 路由到 logging"""
    log_file = tmp_path / "warn.log"
    # py.warnings 是 logging 内部用的 logger
    # 同一进程里别的用例可能关掉了全局日志,这里恢复
    logging.disable(logging.NOTSET)
    logger = logging.getLogger("py.warnings")
    logger.setLevel(logging.WARNING)
    logger.disabled = False
    logger.handlers = []
    handler = logging.FileHandler(str(log_file))
    logger.addHandler(handler)
    # propagate=False 避免被 root 拿走
    logger.propagate = False
    logging.captureWarnings(True)

    import warnings as w
    w.warn("this is a warning", DeprecationWarning)
    handler.flush()
    handler.close()

    content = log_file.read_text()
    assert "this is a warning" in content, f"warning 应在文件, 实际: {content!r}"
    assert "DeprecationWarning" in content, f"DeprecationWarning 应在, 实际: {content!r}"


def test_logging_real_thread_safety(tmp_path):
    """logging 真线程安全: 多线程同时写不丢"""
    import threading
    log_file = tmp_path / "thread.log"
    logger = logging.getLogger("test_logger_thread")
    logger.setLevel(logging.INFO)
    logger.handlers = []
    handler = logging.FileHandler(str(log_file))
    logger.addHandler(handler)

    n_threads = 20
    n_per = 100

    def worker():
        for i in range(n_per):
            logger.info(f"thread_msg_{i}")

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    handler.flush()
    handler.close()

    lines = log_file.read_text().splitlines()
    # 20 * 100 = 2000 行
    assert len(lines) == n_threads * n_per, f"应 {n_threads*n_per} 行, 实际 {len(lines)}"


def test_argparse_real_positional_and_optional():
    """argparse 真解析位置参数 + 可选参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--age", type=int, default=0)
    parser.add_argument("--city", default="unknown")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args(["Alice", "--age", "30", "--city", "Beijing", "-v"])
    assert args.name == "Alice"
    assert args.age == 30
    assert args.city == "Beijing"
    assert args.verbose is True


def test_argparse_real_nargs_variadic():
    """argparse 真支持 nargs='+' / '*' 变长"""
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--tag", action="append")  # 多值

    args = parser.parse_args(["a.txt", "b.txt", "c.txt", "--tag", "v1", "--tag", "v2"])
    assert args.files == ["a.txt", "b.txt", "c.txt"]
    assert args.tag == ["v1", "v2"]


def test_argparse_real_choices_and_type():
    """argparse 真 type 转换 + choices 校验"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["dev", "prod", "staging"], required=True)
    parser.add_argument("--count", type=int)

    # 合法
    args = parser.parse_args(["--mode", "prod", "--count", "42"])
    assert args.mode == "prod"
    assert args.count == 42

    # 非法 mode
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "invalid"])


def test_argparse_real_help_message():
    """argparse 真产 help"""
    parser = argparse.ArgumentParser(description="Test tool")
    parser.add_argument("input")
    parser.add_argument("-o", "--output")

    # 模拟 --help
    with pytest.raises(SystemExit):
        try:
            parser.parse_args(["--help"])
        except SystemExit as e:
            assert e.code == 0
            raise


def test_configparser_real_read_write(tmp_path):
    """configparser 真读写真 INI"""
    ini_file = tmp_path / "test.ini"
    ini_file.write_text("""[DEFAULT]
server = localhost
port = 8000

[dev]
debug = true
log = debug

[prod]
debug = false
log = warning
""")

    cp = configparser.ConfigParser()
    cp.read(str(ini_file))

    # 真读
    assert cp["DEFAULT"]["server"] == "localhost"
    assert cp["DEFAULT"]["port"] == "8000"  # 永远 str
    assert cp["dev"]["debug"] == "true"
    # dev 继承 DEFAULT
    assert cp["dev"]["server"] == "localhost"

    # 写
    cp["new"] = {"key": "value"}
    cp.write(open(str(ini_file), "w"))
    cp2 = configparser.ConfigParser()
    cp2.read(str(ini_file))
    assert cp2["new"]["key"] == "value"


def test_decimal_real_precision_no_float_error():
    """Decimal 真精度: 0.1 + 0.2 精确 = 0.3 (float 不是)"""
    a = Decimal("0.1") + Decimal("0.2")
    assert a == Decimal("0.3"), f"Decimal 0.1+0.2 应 = 0.3, 实际 {a}"
    # 对比 float
    assert 0.1 + 0.2 != 0.3, f"float 0.1+0.2 不 = 0.3, 实际 {0.1 + 0.2}"


def test_decimal_real_rounding_modes():
    """Decimal 真多种 rounding mode"""
    d = Decimal("2.5")
    # ROUND_HALF_EVEN (banker's rounding) — 默认
    assert d.quantize(Decimal("1"), rounding=decimal.ROUND_HALF_EVEN) == Decimal("2")
    # ROUND_HALF_UP
    assert d.quantize(Decimal("1"), rounding=decimal.ROUND_HALF_UP) == Decimal("3")
    # ROUND_DOWN
    assert d.quantize(Decimal("1"), rounding=decimal.ROUND_DOWN) == Decimal("2")


def test_decimal_real_arithmetic_large():
    """Decimal 真大数算 (超 float 精度)"""
    # Decimal 默认 precision=28, 大数会截断; 调高
    import decimal as _dec
    _dec.getcontext().prec = 50
    huge = Decimal("123456789012345678901234567890.123456789")
    result = huge * Decimal("2")
    expected = Decimal("246913578024691357802469135780.246913578")
    # normalize 后比较 (normalize 把尾数转成 unscaled 形式)
    assert result.normalize() == expected.normalize(), (
        f"Decimal 大数算应相等, {result.normalize()} vs {expected.normalize()}"
    )
    # 验 Decimal 真保了 39 位精度 (结果 trailing 数字)
    assert "246913578" in str(result.normalize())
    # 对比: float 失精度 (用真实能验的数)
    # 0.1 + 0.2 验: float 不精确, Decimal 精确
    float_r = 0.1 + 0.2
    decimal_r = Decimal("0.1") + Decimal("0.2")
    assert float_r != 0.3, f"float 0.1+0.2 不 = 0.3, 实际 {float_r}"
    assert decimal_r == Decimal("0.3"), f"Decimal 应 = 0.3, 实际 {decimal_r}"


def test_argparse_real_subcommands():
    """argparse 真 sub-commands"""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    p_etl = sub.add_parser("etl")
    p_etl.add_argument("symbols")

    p_bt = sub.add_parser("backtest")
    p_bt.add_argument("--strategy", required=True)

    args = parser.parse_args(["etl", "600519"])
    assert args.cmd == "etl"
    assert args.symbols == "600519"

    args2 = parser.parse_args(["backtest", "--strategy", "ma_cross"])
    assert args2.cmd == "backtest"
    assert args2.strategy == "ma_cross"
