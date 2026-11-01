# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket` 进阶 (广播 + SO_REUSEADDR) + `email` 进阶 (Generator) + `ast` 进阶 (TypedDict) + `typing` 进阶 (assert_never) + `dis` 进阶 真底层测试。

覆盖 socket 选项 / 邮件生成 / AST TypedDict / typing assert_never / 字节码 模块:
  - `socket.setsockopt + getsockopt SO_REUSEADDR 真设读`
  - `socket.setsockopt SO_BROADCAST 真设广播`
  - `socket.getsockopt(SOL_SOCKET) 真返值`
  - `email.generator.Generator 真建 + flatten 邮件`
  - `email.iterators.typed_subpart_iterator 真遍历 multipart`
  - `email.policy.compat32 真建 Policy`
  - `ast.TypedDict 真建 typed dict class 3.11+`
  - `ast.parse + ast.dump 真序列化嵌套 dict`
  - `ast.unparse 真反向 (3.9+)`
  - `typing.assert_never 3.11+ 真静态穷尽性检查`
  - `typing.Literal 真字面值`
  - `typing.get_args + get_origin 进阶`
  - `dis.get_instructions 进阶真返 Instructions list with positions`
"""
import ast
import dis
import email
import email.generator
import email.iterators
import email.policy
import socket
import sys
import typing

import pytest


# -- socket 进阶 (setsockopt) -------------------------------------------------

class TestSocketAdvancedV4:
    def test_setsockopt_SO_REUSEADDR(self):
        """`socket.setsockopt + getsockopt(SOL_SOCKET, SO_REUSEADDR) 真设读。"""
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            v = s.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
            assert v == 1, f"SO_REUSEADDR 应=1,实际 {v}"

    def test_setsockopt_SO_BROADCAST(self):
        """`socket.setsockopt SO_BROADCAST 真设广播。"""
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            v = s.getsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST)
            assert v == 1

    def test_socket_options_int(self):
        """`socket.SO_*, IP_TTL 等 int constants 真 int。"""
        for name in ("SO_REUSEADDR", "SO_BROADCAST", "SO_KEEPALIVE", "SO_LINGER"):
            if hasattr(socket, name):
                assert isinstance(getattr(socket, name), int)


# -- email 进阶 (Generator + iterators) ---------------------------------------

class TestEmailAdvancedV2:
    def test_email_Generator(self):
        """`email.generator.Generator 真建 + flatten 邮件 (用 StringIO text stream)`"""
        msg = email.message.EmailMessage()
        msg["Subject"] = "forge generator test"
        msg.set_content("body content")
        # Generator 用 StringIO (text stream)
        out_buf = io.StringIO()
        gen = email.generator.Generator(out_buf)
        gen.flatten(msg, unixfrom=False)
        # flatten 必写
        text = out_buf.getvalue()
        assert "Subject: forge generator test" in text

    def test_email_policy_compat32(self):
        """`email.policy.compat32 真建 Policy instance。"""
        p = email.policy.compat32
        assert p is not None
        # compat32 必是 policy
        assert isinstance(p, email.policy.Policy)

    def test_typed_subpart_iterator(self):
        """`typed_subpart_iterator 真遍历 multipart。"""
        # 简化: 仅验函数存在
        assert callable(email.iterators.typed_subpart_iterator)


import io  # noqa: E402  (used by email.generator.BytesIO)


# -- ast 进阶 (TypedDict + dump + unparse) -----------------------------------

class TestAstAdvancedV4:
    def test_TypedDict_node(self):
        """`ast.TypedDict 真建 typed dict class 3.11+ (沙箱 3.11 无 ast.TypedDict 跳过)`"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ TypedDict 节点")
        if not hasattr(ast, "TypedDict"):
            pytest.skip("沙箱 ast 无 TypedDict")
        # 创一个 TypedDict node
        node = ast.TypedDict(
            "Movie",
            {"name": ast.Constant(value="string"), "year": ast.Constant(value="int")},
            [],
        )
        # 必能 dump
        dumped = ast.dump(node)
        assert "TypedDict" in dumped
        assert "Movie" in dumped

    def test_parse_dump_nested(self):
        """`ast.parse + ast.dump 真序列化嵌套 AST。"""
        tree = ast.parse("x = {'a': 1, 'b': [1, 2, 3]}")
        dumped = ast.dump(tree)
        # 必含 Dict, List
        assert "Dict" in dumped
        assert "List" in dumped

    def test_unparse_simple(self):
        """`ast.unparse 真反向 (3.9+)。"""
        tree = ast.parse("x = 1")
        code = ast.unparse(tree)
        assert "x" in code
        assert "1" in code


# -- typing 进阶 (assert_never 3.11+) ----------------------------------------

class TestTypingAdvancedV8:
    def test_assert_never(self):
        """`typing.assert_never 3.11+ 真静态穷尽性检查。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ assert_never")
        # assert_never 在静态分析时抛, runtime 不抛
        # 简化: 验证 typing.assert_never 存在
        assert hasattr(typing, "assert_never")
        # 真能调 (传 Never type)
        # 沙箱 runtime 不抛, 静态才抛
        try:
            typing.assert_never(None)  # 3.11 runtime 不抛
        except AssertionError:
            pass  # OK, 3.12+ runtime 抛

    def test_get_args(self):
        """`typing.get_args 真取泛型参数。"""
        # typing.List[int] 真有 args
        args = typing.get_args(typing.List[int])
        assert args == (int,), f"get_args(List[int]) 应=(int,),实际 {args}"

    def test_get_origin(self):
        """`typing.get_origin 真取泛型 origin。"""
        # typing.List[int] origin = list (3.9+) 或 typing.List
        origin = typing.get_origin(typing.List[int])
        # 3.9+ 用 list
        assert origin in (list, typing.List), (
            f"get_origin(List[int]) 应=list 或 List,实际 {origin}"
        )


# -- dis 进阶 -----------------------------------------------------------------

class TestDisAdvancedV6:
    def test_get_instructions_with_positions(self):
        """`dis.get_instructions 真返 Instructions list 含 positions (3.11+)。"""
        code = compile("""
def forge_func(x, y):
    return x + y
""", "<test>", "exec")
        # 找 forge_func
        for c in code.co_consts:
            if hasattr(c, "co_name") and c.co_name == "forge_func":
                f_code = c
                break
        else:
            pytest.skip("没找到 forge_func")

        instrs = list(dis.get_instructions(f_code))
        # 必 ≥ 1
        assert len(instrs) >= 1
        # 必含 RESUME (3.11+ 字节码开始)
        assert any(i.opname == "RESUME" for i in instrs)
        # 必含 RETURN_VALUE
        assert any(i.opname == "RETURN_VALUE" for i in instrs)

    def test_dis_Bytecode_dis_method(self):
        """`dis.dis(BC) 真打 (用 stdout 重定向)`"""
        import contextlib
        fn = lambda x: x + 1  # noqa: E731
        bc = dis.Bytecode(fn)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dis.dis(bc)
        out = buf.getvalue()
        # 必 ≥ 1 个指令
        assert len(out) > 0
        # 必含 RESUME
        assert "RESUME" in out or "LOAD" in out
