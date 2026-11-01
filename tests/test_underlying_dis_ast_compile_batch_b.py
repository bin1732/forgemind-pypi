# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ast` 方向的底层真实行为测试:语法树构造、遍历、字面量求值与源码定位。

覆盖模块:ast(抽象语法树)。

真实测试项:
  - `ast.parse` 真产出 Module→Assign→BinOp(Add) 结构的语法树
  - `ast.walk` 真按广度优先遍历,节点类型序列与各类型计数可逐项核对
  - `ast.dump` 真渲染出 'Assign(targets=[Name(id=...)]' 结构文本
  - `ast.unparse` 真把语法树还原成源码,还原后重解析结构完全一致
  - `ast.unparse` 真处理 f-string 与星号参数
  - `ast.NodeVisitor` 子类真按节点类型计数
  - `ast.NodeTransformer` 子类真改写节点且改写结果被 unparse 体现
  - `ast.literal_eval` 真求值字面量,非字面量真抛 ValueError
  - `ast.get_source_segment` 真切出原样源码片段
  - `ast.get_docstring` 真取出模块与函数文档串
  - `ast.iter_fields` 真列出节点字段名
  - `ast.parse(type_comments=True)` 真记录类型注释
  - `ast.increment_lineno` 真整体平移所有节点行号
  - `ast.fix_missing_locations` 真补齐缺失的行列信息
  - `ast.parse(mode="eval")` 真产出 Expression 树
  - `ast.parse` 真解析 match/case 结构化模式匹配
  - `ast.TypeAlias` 节点(3.12+)真承载 type 语句
"""

import ast

import pytest


class _VisitCounter(ast.NodeVisitor):
    """统计各类型节点访问次数的访问器。"""

    def __init__(self):
        self.functions = 0
        self.calls = 0
        self.names = []

    def visit_FunctionDef(self, node):
        self.functions += 1
        self.generic_visit(node)

    def visit_Call(self, node):
        self.calls += 1
        self.generic_visit(node)

    def visit_Name(self, node):
        self.names.append(node.id)
        self.generic_visit(node)


class _OneToTwo(ast.NodeTransformer):
    """把常量 1 改写成常量 2 的改写器。"""

    def visit_Constant(self, node):
        if node.value == 1:
            return ast.copy_location(ast.Constant(value=2), node)
        return node


class TestAstParsing:
    def test_ast_parse_builds_expected_tree_shape(self):
        """`ast.parse("x = 1 + 2")` 真产出 Module→Assign→BinOp(Add) 结构,常量分别是 1 与 2。"""
        tree = ast.parse("x = 1 + 2\n")
        assert isinstance(tree, ast.Module)
        assert len(tree.body) == 1
        assign = tree.body[0]
        assert isinstance(assign, ast.Assign)
        assert len(assign.targets) == 1
        assert assign.targets[0].id == "x"
        assert isinstance(assign.value, ast.BinOp)
        assert isinstance(assign.value.op, ast.Add)
        assert assign.value.left.value == 1
        assert assign.value.right.value == 2

    def test_ast_parse_eval_mode_returns_expression_tree(self):
        """`ast.parse("1 + 2", mode="eval")` 真产出 Expression 树,body 是 BinOp。"""
        tree = ast.parse("1 + 2", mode="eval")
        assert isinstance(tree, ast.Expression)
        assert isinstance(tree.body, ast.BinOp)
        assert tree.body.left.value == 1
        assert tree.body.right.value == 2

    def test_ast_parse_type_comments_records_type_annotations(self):
        """`type_comments=True` 真记录 '# type: int' 与 '(int) -> None',默认解析不记录。"""
        source = "x = 1  # type: int\ndef f(a):\n    # type: (int) -> None\n    pass\n"
        typed = ast.parse(source, type_comments=True)
        assert typed.body[0].type_comment == "int"
        assert typed.body[1].type_comment == "(int) -> None"
        plain = ast.parse(source)
        assert plain.body[0].type_comment is None
        assert plain.body[1].type_comment is None

    def test_ast_match_statement_parses_pattern_cases(self):
        """`match` 语句真解析出 ast.Match:subject 是 Call,case 模式是 MatchSequence。"""
        tree = ast.parse("match command.split():\n    case [action]:\n        pass\n")
        match_node = tree.body[0]
        assert isinstance(match_node, ast.Match)
        assert isinstance(match_node.subject, ast.Call)
        assert len(match_node.cases) == 1
        pattern = match_node.cases[0].pattern
        assert isinstance(pattern, ast.MatchSequence)
        assert pattern.patterns[0].name == "action"

    @pytest.mark.skipif(
        not hasattr(ast, "TypeAlias"),
        reason="ast.TypeAlias 节点需要 Python 3.12+",
    )
    def test_ast_type_alias_statement_carries_name_and_value(self):
        """3.12+ 的 `type X = int` 真解析出 ast.TypeAlias 节点,名字为 X,值为 int 类型。"""
        tree = ast.parse("type X = int\n")
        alias = tree.body[0]
        assert isinstance(alias, ast.TypeAlias)
        assert alias.name.id == "X"
        assert alias.value.value is int


class TestAstTraversal:
    def test_ast_walk_traverses_breadth_first_with_exact_type_counts(self):
        """`ast.walk` 真按广度优先遍历:8 个节点的类型序列与各类型计数逐项可核对。"""
        nodes = list(ast.walk(ast.parse("def f():\n    return g(1)\n")))
        assert len(nodes) == 8
        assert [type(node).__name__ for node in nodes] == [
            "Module",
            "FunctionDef",
            "arguments",
            "Return",
            "Call",
            "Name",
            "Constant",
            "Load",
        ]
        assert sum(1 for node in nodes if isinstance(node, ast.FunctionDef)) == 1
        assert sum(1 for node in nodes if isinstance(node, ast.arguments)) == 1
        assert sum(1 for node in nodes if isinstance(node, ast.Return)) == 1
        assert sum(1 for node in nodes if isinstance(node, ast.Call)) == 1
        assert sum(1 for node in nodes if isinstance(node, ast.Name)) == 1
        assert sum(1 for node in nodes if isinstance(node, ast.Constant)) == 1

    def test_ast_node_visitor_counts_named_visits(self):
        """自定义 `ast.NodeVisitor` 真统计出 1 个函数定义、1 次调用与名字 'g'。"""
        counter = _VisitCounter()
        counter.visit(ast.parse("def f():\n    return g(1)\n"))
        assert counter.functions == 1
        assert counter.calls == 1
        assert counter.names == ["g"]

    def test_ast_node_transformer_rewrites_constants(self):
        """自定义 `ast.NodeTransformer` 真把常量 1 改写成 2,unparse 结果为 'x = 2'。"""
        tree = _OneToTwo().visit(ast.parse("x = 1\n"))
        assert ast.unparse(tree) == "x = 2"

    def test_ast_iter_fields_exposes_node_attributes(self):
        """`ast.iter_fields` 真列出 Assign 的 targets/value/type_comment 与函数节点的 args/body/returns。"""
        assign = ast.parse("x = 1\n").body[0]
        assert [name for name, _ in ast.iter_fields(assign)] == [
            "targets",
            "value",
            "type_comment",
        ]
        function = ast.parse("def f(a):\n    return a\n").body[0]
        field_names = [name for name, _ in ast.iter_fields(function)]
        assert "name" in field_names
        assert "args" in field_names
        assert "body" in field_names
        assert "returns" in field_names
        assert "decorator_list" in field_names


class TestAstRendering:
    def test_ast_dump_renders_structural_representation(self):
        """`ast.dump` 真渲染出 'Assign(targets=[Name(id='x', ctx=Store())]' 结构文本。"""
        tree = ast.parse("x = 1 + 2\n")
        dumped = ast.dump(tree)
        assert "Assign(targets=[Name(id='x', ctx=Store())]" in dumped
        assert "BinOp(left=Constant(value=1), op=Add(), right=Constant(value=2))" in dumped
        indented = ast.dump(tree, indent=2)
        assert indented.startswith("Module(\n  body=[\n")
        assert indented.count("\n") > dumped.count("\n")

    def test_ast_unparse_round_trip_keeps_semantics(self):
        """`ast.unparse` 真还原源码文本,还原结果重解析后的树与原树逐字段一致。"""
        source = "def f(a, b=2):\n    return a * b + 1\n"
        tree = ast.parse(source)
        text = ast.unparse(tree)
        assert text == "def f(a, b=2):\n    return a * b + 1"
        assert ast.dump(ast.parse(text)) == ast.dump(tree)

    def test_ast_unparse_handles_fstring_and_starred_arguments(self):
        """`ast.unparse` 真处理 f-string 的转换与格式说明,以及 *args/**kwargs 调用。"""
        assert ast.unparse(ast.parse('x = f"a{b!r:>10}"')) == "x = f'a{b!r:>10}'"
        assert ast.unparse(ast.parse("f(*a, **b)")) == "f(*a, **b)"
        assert ast.unparse(ast.parse("x = [1, 2, 3]")) == "x = [1, 2, 3]"

    def test_ast_get_source_segment_returns_exact_source_text(self):
        """`ast.get_source_segment` 真切出原样源码片段:语句 'return a + 1' 与实参 'a'。"""
        source = "def f(a):\n    return a + 1\n"
        tree = ast.parse(source)
        function = tree.body[0]
        assert ast.get_source_segment(source, function.body[0]) == "return a + 1"
        assert ast.get_source_segment(source, function.args.args[0]) == "a"

    def test_ast_get_docstring_reads_module_and_function_docstrings(self):
        """`ast.get_docstring` 真取出模块与函数文档串,无文档串时返回 None。"""
        module = ast.parse('"""模块说明"""\n')
        assert ast.get_docstring(module) == "模块说明"
        function_tree = ast.parse('def f():\n    """函数说明"""\n    pass\n')
        assert ast.get_docstring(function_tree.body[0]) == "函数说明"
        assert ast.get_docstring(ast.parse("x = 1\n")) is None


class TestAstEvaluation:
    def test_ast_literal_eval_computes_real_literals(self):
        """`ast.literal_eval` 真求值字面量:列表/元组、字典、字符串、None 与负数。"""
        assert ast.literal_eval("[1, 2, (3, 4)]") == [1, 2, (3, 4)]
        assert ast.literal_eval("{'a': 1, 'b': [2, 3]}") == {"a": 1, "b": [2, 3]}
        assert ast.literal_eval("'ab'") == "ab"
        assert ast.literal_eval("None") is None
        assert ast.literal_eval("-5") == -5

    def test_ast_literal_eval_rejects_non_literal_expressions(self):
        """`ast.literal_eval` 遇到 BinOp 与 Call 真抛 ValueError,提示 malformed node or string。"""
        with pytest.raises(ValueError, match="malformed node or string"):
            ast.literal_eval("1 + 1")
        with pytest.raises(ValueError, match="malformed node or string"):
            ast.literal_eval("f()")


class TestAstPosition:
    def test_ast_increment_lineno_shifts_all_line_numbers(self):
        """`ast.increment_lineno` 真把全部节点行号整体加 1:body 行号由 [1, 2] 变 [2, 3]。"""
        tree = ast.parse("x = 1\ny = 2\n")
        assert [node.lineno for node in tree.body] == [1, 2]
        ast.increment_lineno(tree)
        assert [node.lineno for node in tree.body] == [2, 3]

    def test_ast_fix_missing_locations_fills_absent_positions(self):
        """`ast.fix_missing_locations` 真给缺行列信息的节点补上 lineno=1、col_offset=0。"""
        module = ast.Module(
            body=[ast.Expr(value=ast.Constant(value=1))],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)
        expression = module.body[0]
        assert expression.lineno == 1
        assert expression.col_offset == 0
        assert expression.end_lineno == 1
        assert expression.end_col_offset == 0
