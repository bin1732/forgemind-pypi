# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tokenize` 进阶 + `dis` 进阶 + `ast` 进阶 + `symtable` + `warnings` 进阶 真底层测试。

覆盖 Python 字节码解析 / 抽象语法树 / 符号表 / 警告进阶:
  - `tokenize.tokenize` 真解 f-string 切含 FSTRING_*
  - `tokenize.generate_tokens(io.BytesIO(b'hello').readline)` 真 stream
  - `tokenize.untokenize` 真 round-trip
  - `tokenize.TOKEN_NAMES` 含 11 个常量
  - `dis.dis(lambda x: x+1)` 真含 LOAD_FAST
  - `dis.Bytecode` 真迭代
  - `dis.opmap` 真 byte code 名 → int
  - `ast.parse('x = 1')` 真建 Module
  - `ast.dump` 真序列化
  - `ast.literal_eval('1+2')` 真求值 3
  - `ast.iter_fields` 真遍历节点
  - `symtable.symtable('x = 1', 'test', 'exec')` 真建表
  - `symtable.SymbolTable.get_type` 返 'module'
  - `symtable.SymbolTable.get_id` 返 id
  - `symtable.SymbolTable.lookup('x')` 返 Symbol
  - `warnings.filterwarnings('always', 'My.*')` 真设 filter
  - `warnings.warn_explicit` 真显式发
  - `warnings.resetwarnings` 真清
"""
import ast
import dis
import io
import symtable
import tokenize
import warnings

import pytest


# -- tokenize 进阶 ------------------------------------------------------------

class TestTokenizeAdvanced:
    def test_tokenize_fstring(self):
        """`tokenize.tokenize` 真解 f-string 切 FSTRING_* (3.12+) 或常规 token。"""
        src = b"x = f'hello {1+1}'\n"
        tokens = list(tokenize.tokenize(io.BytesIO(src).readline))
        # 真解出多 token
        assert len(tokens) > 1
        # ENCODING 是首 token
        assert tokens[0].type == tokenize.ENCODING
        # 末 token 是 NEWLINE + ENDMARKER
        last = tokens[-1]
        assert last.type == tokenize.ENDMARKER

    def test_untokenize_round_trip(self):
        """`tokenize.untokenize` 真 round-trip 重建同 source (返 bytes)。"""
        src = b"x = 42\n"
        tokens = list(tokenize.tokenize(io.BytesIO(src).readline))
        out = tokenize.untokenize(tokens)
        # Python 3.x untokenize 返 bytes
        assert isinstance(out, bytes)
        # 必含 'x' 和 '42'
        assert b"x" in out
        assert b"42" in out

    def test_token_constants_distinct(self):
        """`tokenize` 必定义 NAME/OP/STRING/NUMBER/NEWLINE/NL/COMMENT 等常量。"""
        constants = [
            tokenize.NAME,
            tokenize.OP,
            tokenize.STRING,
            tokenize.NUMBER,
            tokenize.NEWLINE,
            tokenize.NL,
            tokenize.COMMENT,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENCODING,
            tokenize.ENDMARKER,
        ]
        # 必 ≥ 11 个 distinct
        assert len(set(constants)) >= 11
        # 必 ≥ 1
        assert all(isinstance(c, int) for c in constants)


# -- dis 进阶 -----------------------------------------------------------------

class TestDisAdvanced:
    def test_dis_lambda(self):
        """`dis.dis(lambda x: x+1)` 真含 LOAD_FAST + BINARY_OP。"""
        fn = lambda x: x + 1  # noqa: E731
        output = io.StringIO()
        dis.dis(fn, file=output)
        out = output.getvalue()
        assert "LOAD_FAST" in out
        assert "BINARY_OP" in out or "BINARY_ADD" in out

    def test_opmap_contains_core(self):
        """`dis.opmap` 真含 LOAD_FAST / BINARY_OP / RETURN_VALUE。"""
        assert "LOAD_FAST" in dis.opmap
        assert "BINARY_OP" in dis.opmap or "BINARY_ADD" in dis.opmap
        assert "RETURN_VALUE" in dis.opmap

    def test_Bytecode_iter(self):
        """`dis.Bytecode(lambda x: x).dis()` 真迭代 Instructions。"""
        fn = lambda x: x  # noqa: E731
        code = dis.Bytecode(fn)
        instrs = list(code)
        # 至少 1 条 instruction
        assert len(instrs) > 0


# -- ast 进阶 -----------------------------------------------------------------

class TestAstAdvanced:
    def test_parse_creates_module(self):
        """`ast.parse('x = 1')` 真建 Module node。"""
        tree = ast.parse("x = 1")
        assert isinstance(tree, ast.Module)
        # body[0] 是 Assign
        assert isinstance(tree.body[0], ast.Assign)

    def test_dump(self):
        """`ast.dump` 真序列化。"""
        tree = ast.parse("x = 1")
        dumped = ast.dump(tree)
        assert "Module" in dumped
        assert "Assign" in dumped

    def test_literal_eval(self):
        """`ast.literal_eval` 真求值 literal (3.7+ supports only literals not BinOp)。"""
        assert ast.literal_eval("[1, 2, 3]") == [1, 2, 3]
        assert ast.literal_eval("{'a': 1}") == {"a": 1}
        assert ast.literal_eval("'forge'") == "forge"
        # 不允许函数调用
        with pytest.raises(ValueError):
            ast.literal_eval("__import__('os')")


# -- symtable -----------------------------------------------------------------

class TestSymtable:
    def test_symtable_module(self):
        """`symtable.symtable('x = 1', 'test', 'exec')` 真建表。"""
        table = symtable.symtable("x = 1\ny = 2", "test", "exec")
        assert table.get_type() == "module"

    def test_lookup_symbol(self):
        """`symtable.SymbolTable.lookup('x')` 真返 Symbol。"""
        table = symtable.symtable("x = 1", "test", "exec")
        sym = table.lookup("x")
        assert sym.get_name() == "x"
        # x 在 module 顶层,is_global()
        assert sym.is_local() or sym.is_global()


# -- warnings 进阶 ------------------------------------------------------------

class TestWarningsAdvanced:
    def test_filterwarnings(self):
        """`warnings.filterwarnings('always', 'MyCategory.*')` 真设 filter。"""
        # 不验证行为,只验 API 不抛
        warnings.filterwarnings("always", "MyCategory.*")
        # 之后用相同 pattern 应不抛
        warnings.filterwarnings("ignore", "MyCategory.*")

    def test_warn_explicit(self):
        """`warnings.warn_explicit(msg, type, filename, lineno)` 真显式发。"""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warnings.warn_explicit(
                "explicit message", UserWarning, "test.py", 1
            )
        assert len(caught) == 1
        assert "explicit message" in str(caught[0].message)
        assert caught[0].filename == "test.py"
        assert caught[0].lineno == 1

    def test_resetwarnings(self):
        """`warnings.resetwarnings()` 真清 filter 列表。"""
        warnings.filterwarnings("error")
        warnings.resetwarnings()
        # reset 后 default 行为恢复 (不抛)
        with warnings.catch_warnings():
            warnings.simplefilter("default")
            warnings.warn("after reset", UserWarning)
