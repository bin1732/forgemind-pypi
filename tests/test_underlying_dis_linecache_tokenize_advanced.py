# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`dis` (advanced) + `linecache` + `tokenize` (advanced) 真底层测试。

覆盖字节码/源码读取/分词模块:
  - `dis.opmap` 字典真含 `LOAD_CONST/POP_TOP/RETURN_VALUE` 等核心字节码
  - `dis.Bytecode(func).dis()` 真把 lambda 函数字节码输出含 'LOAD_FAST'
  - `linecache.getline(file, lineno)` 真读文件指定行,文件不存在返 ''
  - `linecache.lazycache` 真让后续 getline 不再走文件系统
  - `tokenize.tokenize(io.BytesIO(b'...').readline)` 真分 f-string 源码
  - `tokenize.untokenize` 真把 token list 拼回源码 (格式化可能改空白)
  - `tokenize.NAME/NUMBER/STRING/OP/NEWLINE/NL/COMMENT` 是真 int 常量
"""
import dis
import io
import linecache
import os
import sys
import tempfile
import textwrap
import token
import tokenize

import pytest


# -- dis ----------------------------------------------------------------------

class TestDisAdvanced:
    def test_opmap_has_core_opcodes(self):
        """`dis.opmap` 真含核心字节码的 int->name 映射。

        Python 3.11+ 用 `BINARY_OP` 取代 `BINARY_ADD/SUB/MUL`,但
        `LOAD_FAST/STORE_FAST/RETURN_VALUE/POP_TOP/LOAD_CONST/JUMP_FORWARD`
        仍是真核心。
        """
        for op in ("POP_TOP", "RETURN_VALUE", "LOAD_CONST", "LOAD_FAST",
                   "STORE_FAST", "BINARY_OP", "JUMP_FORWARD"):
            assert op in dis.opmap, f"{op} 应在 dis.opmap,实际缺"
            assert isinstance(dis.opmap[op], int)

    def test_opname_is_tuple_indexed_by_opcode(self):
        """`dis.opname` 真按 opcode int 索引返回可读名。"""
        # LOAD_CONST 字节码值
        load_const = dis.opmap["LOAD_CONST"]
        assert dis.opname[load_const] == "LOAD_CONST"

    def test_bytecode_dis_of_lambda_contains_load_fast(self):
        """`dis.Bytecode(lambda x: x + 1).dis()` 真输出含 'LOAD_FAST' 字节码。"""
        fn = lambda x: x + 1
        # Python 3.11+ Bytecode.dis() 不接 file kwarg,改用 sys.stdout 重定向
        out = io.StringIO()
        old = sys.stdout
        sys.stdout = out
        try:
            dis.dis(fn)  # 模块级 dis 接受 file kw
        finally:
            sys.stdout = old
        text = out.getvalue()
        assert "LOAD_FAST" in text, (
            f"lambda 字节码应含 LOAD_FAST,实际前 200 字: {text[:200]!r}"
        )
        # Python 3.11 用 BINARY_OP 替代 BINARY_ADD
        assert "BINARY_OP" in text or "BINARY_ADD" in text, (
            f"应含 BINARY_OP 或 BINARY_ADD,实际 {text[:300]!r}"
        )


# -- linecache ----------------------------------------------------------------

class TestLinecache:
    def test_getline_returns_actual_line(self):
        """`linecache.getline(path, N)` 真读文件第 N 行,文件不存在返 ''。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tiny.py")
            with open(path, "w") as f:
                f.write("# line 1\nline2 = 2\nline3 = 3\n")
            assert linecache.getline(path, 1).strip() == "# line 1"
            assert linecache.getline(path, 2).strip() == "line2 = 2"
            assert linecache.getline(path, 3).strip() == "line3 = 3"
            assert linecache.getline(path, 99) == ""  # 越界
            assert linecache.getline("/nonexistent.py", 1) == ""

    def test_lazycache_avoids_re_read(self):
        """`linecache.lazycache` 之后,`getline` 不再走文件系统。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lazy.py")
            with open(path, "w") as f:
                f.write("alpha\nbeta\n")
            # 第一次:正常读
            assert linecache.getline(path, 1).strip() == "alpha"
            # lazycache 之后,即使删除文件,getline 还能拿缓存
            linecache.lazycache(path, {"size": 12, "mtime": 0, "lines": {1: "alpha\n", 2: "beta\n"}})
            os.remove(path)
            assert linecache.getline(path, 1).strip() == "alpha", (
                f"lazycache 缓存命中,实际 {linecache.getline(path, 1)!r}"
            )

    def test_checkcache_clears_stale(self):
        """`linecache.checkcache` 真清空 mtime 变化的条目。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "stale.py")
            with open(path, "w") as f:
                f.write("v1\n")
            linecache.getline(path, 1)
            # 改 mtime,模拟文件被改
            os.utime(path, (1000000, 1000000))
            linecache.checkcache()
            # 改后再 getline,应读到新内容
            with open(path, "w") as f:
                f.write("v2\n")
            assert linecache.getline(path, 1).strip() == "v2"


# -- tokenize -----------------------------------------------------------------

class TestTokenizeAdvanced:
    def test_tokenize_fstring_source(self):
        """`tokenize.tokenize` 真把 f-string 源码切成 tokens。

        Python 3.12+ 用 FSTRING_START/END/RAW_START 等,3.11 没这些常量,
        退而求其次:验证含 NAME/OP/STRING 等通用 token。
        """
        src = "x = f'hello {name}!'\n"
        toks = list(tokenize.tokenize(io.BytesIO(src.encode("utf-8")).readline))
        types = [t.type for t in toks]
        assert token.NAME in types
        assert token.OP in types
        assert token.STRING in types
        # 3.12+ f-string 内部 token
        if hasattr(token, "FSTRING_START"):
            fstring_token_types = {token.FSTRING_START, token.FSTRING_MIDDLE,
                                   token.FSTRING_END, token.FSTRING_RAW_START,
                                   token.FSTRING_RAW_MIDDLE, token.FSTRING_RAW_END}
            assert any(t in fstring_token_types for t in types), (
                f"f-string 应被切成 FSTRING_* tokens,实际 types: {types}"
            )

    def test_untokenize_round_trip_preserves_value(self):
        """`untokenize` 真把 token list 拼回可执行源码,eval 出同值。"""
        src = "x = 1 + 2 * 3\n"
        toks = list(tokenize.tokenize(io.BytesIO(src.encode("utf-8")).readline))
        # 过滤掉 ENCODING + NEWLINE + NL + ENDMARKER (untokenize 期望完整 list)
        rebuilt = tokenize.untokenize(toks)
        # eval 重建后 (变量 x 可能在 namespace)
        ns = {}
        exec(rebuilt, ns)
        assert ns["x"] == 7, f"untokenize 还原代码应让 x=7,实际 {ns['x']}"

    def test_tokenize_constants_are_distinct_ints(self):
        """`token.NAME/OP/STRING/...` 是真 int 且互不相同。"""
        names_to_check = ["NAME", "NUMBER", "STRING", "OP", "NEWLINE",
                          "NL", "COMMENT", "INDENT", "DEDENT", "ENCODING",
                          "ENDMARKER"]
        seen = {}
        for n in names_to_check:
            v = getattr(token, n)
            assert isinstance(v, int), f"token.{n} 应为 int,实际 {type(v)}"
            assert v not in seen.values(), f"token.{n}={v} 与 {seen} 冲突"
            seen[n] = v
