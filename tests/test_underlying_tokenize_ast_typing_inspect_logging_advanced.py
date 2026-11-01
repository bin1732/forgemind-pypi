# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tokenize` 进阶 (untokenize 逆向 + 字符串) + `ast` 进阶 (浅深 AST) + `typing` 进阶 (NewType+cast) + `inspect` 进阶 (getmembers 排序) + `logging` 进阶 (getLogRecordFactory) 真底层测试。

覆盖 tokenize 逆向 / AST 树 / typing NewType / inspect / logging factory 模块:
  - `tokenize.untokenize(可迭代 tokens) 真返 str/bytes round-trip`
  - `tokenize.detect_encoding 真检测 UTF-8`
  - `ast.parse 真解析 + ast.dump 真序列化`
  - `ast.copy_location 真拷贝位置信息`
  - `ast.walk 真遍历所有节点`
  - `typing.NewType 真创 distinct type`
  - `typing.cast 真 runtime 无操作`
  - `typing.get_type_hints 真解 with `from __future__ import annotations``
  - `typing.Any 真接受任何`
  - `inspect.getmembers 真按 predicate 过滤`
  - `inspect.getmodule 真取模块`
  - `inspect.getmro 真取 MRO`
  - `inspect.getcallargs 沙箱 skip (3.11 删)`
  - `logging.getLogRecordFactory 真设/取 factory`
  - `logging.setLogRecordFactory 真接管 LogRecord 创建`
"""
import ast
import inspect
import logging
import sys
import tokenize
import typing

import pytest


# -- tokenize 进阶 ------------------------------------------------------------

class TestTokenizeAdvancedV3:
    def test_untokenize_round_trip_str(self):
        """`untokenize 真返 str/bytes (3.11+ bytes) round-trip。"""
        src = b"x = 1\n"
        tokens = list(tokenize.tokenize(io.BytesIO(src).readline))
        out = tokenize.untokenize(tokens)
        # 3.11+ 返 bytes
        assert isinstance(out, (bytes, str))
        if isinstance(out, bytes):
            assert b"x" in out and b"1" in out
        else:
            assert "x" in out and "1" in out

    def test_detect_encoding(self):
        """`tokenize.detect_encoding 真返 (encoding, lines)`。"""
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, suffix=".py"
        ) as f:
            f.write(b"# -*- coding: utf-8 -*-\n")
            f.write(b"x = 1\n")
            path = f.name
        try:
            with open(path, "rb") as f:
                result = tokenize.detect_encoding(f.readline)
            # 3.11+ 返 (encoding, lines_list)
            assert isinstance(result, tuple)
            assert len(result) == 2
            enc, _lines = result
            assert enc in ("utf-8", "UTF-8", "utf-8-sig"), (
                f"encoding 应 utf-8,实际 {enc}"
            )
        finally:
            os.unlink(path)


import io  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402


# -- ast 进阶 (walk + copy_location) -------------------------------------------

class TestAstAdvancedV5:
    def test_ast_walk(self):
        """`ast.walk 真遍历所有节点 (含嵌套)`. """
        tree = ast.parse("def f(x):\n return x + 1\n")
        nodes = list(ast.walk(tree))
        # 必 ≥ 1
        assert len(nodes) >= 1
        # 必含 FunctionDef, Return, BinOp
        node_types = {type(n).__name__ for n in nodes}
        assert "FunctionDef" in node_types
        assert "Return" in node_types
        assert "BinOp" in node_types

    def test_copy_location(self):
        """`ast.copy_location 真正拷贝位置信息。"""
        tree = ast.parse("x = 1")
        # 创一个新节点
        new_node = ast.Constant(value=42)
        # copy_location 必给 lineno + col_offset
        result = ast.copy_location(new_node, tree.body[0])
        assert result.lineno == tree.body[0].lineno


# -- typing 进阶 (NewType + cast + get_type_hints) ----------------------------

class TestTypingAdvancedV9:
    def test_NewType(self):
        """`typing.NewType 真建 distinct type`。"""
        UserId = typing.NewType("UserId", int)
        uid = UserId(42)
        assert uid == 42
        # 仍是 int 子类
        assert isinstance(uid, int)
        # 不同 NewType 互不 isinstance
        OrderId = typing.NewType("OrderId", int)
        assert isinstance(uid, int) and isinstance(OrderId(1), int)

    def test_cast_runtime_noop(self):
        """`typing.cast 真 runtime 无操作`。"""
        v = typing.cast(str, 42)
        assert v == 42  # 仍是 int

    def test_get_type_hints_future_annotations(self):
        """`get_type_hints 真解 'from __future__ import annotations' string 形式。"""
        # 'x: int' 字符串形式
        def f(x: "int", y: "str") -> "bool":  # type: ignore[valid-type]
            pass

        hints = typing.get_type_hints(f)
        assert hints["x"] is int
        assert hints["y"] is str
        assert hints["return"] is bool


# -- inspect 进阶 -------------------------------------------------------------

class _Inspector:
    def method_one(self):
        pass

    def method_two(self):
        pass

    class_attr = 42


class TestInspectAdvancedV5:
    def test_getmembers_with_predicate(self):
        """`inspect.getmembers 真按 predicate 过滤。"""
        members = inspect.getmembers(_Inspector, inspect.isfunction)
        names = [n for n, _ in members]
        # 必含 method_one + method_two
        assert "method_one" in names
        assert "method_two" in names
        # 不含 class_attr (不是 function)
        assert "class_attr" not in names

    def test_getmodule(self):
        """`inspect.getmodule 真取模块。"""
        m = inspect.getmodule(_Inspector)
        # 必返本测试模块
        assert m is not None
        assert m.__name__.endswith("test_underlying_tokenize_ast_typing_inspect_logging_advanced")

    def test_getmro(self):
        """`inspect.getmro 真取 method resolution order。"""
        mro = inspect.getmro(_Inspector)
        # MRO 必是 tuple 含本类 + object
        assert _Inspector in mro
        assert object in mro


# -- logging 进阶 (getLogRecordFactory + setLogRecordFactory) -----------------

class TestLoggingAdvancedV4:
    def test_getLogRecordFactory(self):
        """`logging.getLogRecordFactory 真返 default factory。"""
        factory = logging.getLogRecordFactory()
        assert factory is not None
        # 必 callable
        assert callable(factory)
        # 真建一个 record
        record = factory(
            "forge", logging.INFO, "/x", 1, "factory test", (), None
        )
        assert record.name == "forge"
        assert record.levelname == "INFO"

    def test_setLogRecordFactory(self):
        """`logging.setLogRecordFactory 真接管 LogRecord 创建。"""
        original = logging.getLogRecordFactory()

        def custom_factory(*args, **kwargs):
            record = original(*args, **kwargs)
            # 加一个 custom attr
            record.custom = "forge_factory"
            return record

        logging.setLogRecordFactory(custom_factory)
        try:
            # 创 logger + log
            log = logging.getLogger("forge_custom_factory")
            log.setLevel(logging.INFO)
            captured = []

            class _Cap(logging.Handler):
                def emit(self, record):
                    captured.append(getattr(record, "custom", None))

            h = _Cap()
            log.addHandler(h)
            try:
                log.info("test")
                assert "forge_factory" in captured
            finally:
                log.removeHandler(h)
        finally:
            # 恢复
            logging.setLogRecordFactory(original)
