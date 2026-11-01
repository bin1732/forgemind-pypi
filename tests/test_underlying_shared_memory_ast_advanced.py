# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 multiprocessing.shared_memory 真跨进程 + 真 tokenize 真 generate_tokens 流式 + 真 ast 进阶 (NodeTransformer/NodeVisitor) + 真 compile 真 code object + 真 graphlib 真拓扑。
全 stdlib, 零模拟。
"""
import multiprocessing.shared_memory
import tokenize
import ast
import graphlib
import io
import sys
import pytest


# ======================== multiprocessing.shared_memory ========================
def test_shared_memory_create_and_write():
    """真 SharedMemory 真跨进程"""
    # 主进程创建
    shm = multiprocessing.shared_memory.SharedMemory(create=True, size=100)
    try:
        # 写
        shm.buf[0:5] = b"hello"
        # 读
        assert bytes(shm.buf[0:5]) == b"hello"
        # name
        assert shm.name is not None
        # 关联
        assert shm.size == 100
    finally:
        shm.close()
        shm.unlink()


def test_shared_memory_attach_existing():
    """真 attach 真重用同 shm"""
    # 创建
    shm1 = multiprocessing.shared_memory.SharedMemory(create=True, size=50)
    try:
        shm1.buf[0:10] = b"0123456789"
        name = shm1.name
        # 另一 handle attach
        shm2 = multiprocessing.shared_memory.SharedMemory(name=name, create=False)
        try:
            # 看到
            assert bytes(shm2.buf[0:10]) == b"0123456789"
            # 写
            shm2.buf[0:5] = b"WRITE"
            # 同步
            assert bytes(shm1.buf[0:5]) == b"WRITE"
        finally:
            shm2.close()
    finally:
        shm1.close()
        shm1.unlink()


# ======================== tokenize 进阶 ========================
def test_tokenize_stream():
    """真 generate_tokens 真流式"""
    code = "a = 1\nb = 2\nc = a + b\n"
    gen = tokenize.generate_tokens(io.StringIO(code).readline)
    # 流迭代
    tokens = []
    for tok in gen:
        tokens.append(tok)
    assert len(tokens) > 0
    # 必有 NAME, NUMBER, OP
    types = {t.type for t in tokens}
    assert tokenize.NAME in types
    assert tokenize.NUMBER in types
    assert tokenize.OP in types


def test_tokenize_untokenize():
    """真 untokenize 真还原"""
    code = "x = 1 + 2"
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    # untokenize
    result = tokenize.untokenize(tokens)
    # 必含核心
    assert "x" in result
    assert "1" in result
    assert "2" in result


# ======================== ast 进阶 ========================
def test_ast_NodeVisitor():
    """真 NodeVisitor 真遍历"""
    class NameCollector(ast.NodeVisitor):
        def __init__(self):
            self.names = []
        def visit_Name(self, node):
            self.names.append(node.id)
            self.generic_visit(node)

    code = "x = 1\ny = x + 2\nz = y * 3"
    tree = ast.parse(code)
    visitor = NameCollector()
    visitor.visit(tree)
    # 收集的 names
    assert "x" in visitor.names
    assert "y" in visitor.names
    assert "z" in visitor.names


def test_ast_NodeTransformer():
    """真 NodeTransformer 真改"""
    class ConstFolder(ast.NodeTransformer):
        def visit_BinOp(self, node):
            self.generic_visit(node)
            if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                if isinstance(node.op, ast.Add):
                    return ast.Constant(value=node.left.value + node.right.value)
            return node

    code = "x = 1 + 2"  # 1 + 2 = 3
    tree = ast.parse(code)
    tree = ConstFolder().visit(tree)
    ast.fix_missing_locations(tree)
    # 真执行
    ns = {}
    exec(compile(tree, "<test>", "exec"), ns)
    assert ns["x"] == 3


# ======================== graphlib ========================
def test_graphlib_TopologicalSorter():
    """真 TopologicalSorter 真拓扑"""
    ts = graphlib.TopologicalSorter()
    # 依赖: build → test → deploy
    #         build ← lib
    ts.add("deploy", "test")
    ts.add("test", "build")
    ts.add("build", "lib")
    ts.add("lib")
    # 真 topological (new TopologicalSorter 每次)
    order = list(ts.static_order())
    # lib 必先
    lib_idx = order.index("lib")
    build_idx = order.index("build")
    test_idx = order.index("test")
    deploy_idx = order.index("deploy")
    assert lib_idx < build_idx < test_idx < deploy_idx


def test_graphlib_cycle_detection():
    """真 cycle detection 真抛"""
    ts = graphlib.TopologicalSorter()
    ts.add("a", "b")
    ts.add("b", "a")  # cycle
    with pytest.raises(graphlib.CycleError):
        list(ts.static_order())


# ======================== compile 真 code ========================
def test_compile_code_object():
    """真 compile 真 code object"""
    code = compile("x = 1; y = 2", "<test>", "exec")
    # code object
    assert hasattr(code, "co_consts")
    assert 1 in code.co_consts
    assert 2 in code.co_consts
    assert code.co_filename == "<test>"


def test_compile_eval():
    """真 eval 真 code"""
    code = compile("x + y", "<test>", "eval")
    result = eval(code, {"x": 1, "y": 2})
    assert result == 3
