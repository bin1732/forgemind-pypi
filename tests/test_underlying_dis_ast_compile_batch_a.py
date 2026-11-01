# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`dis` 方向的底层真实行为测试:字节码反汇编、opcode 元数据与栈效果。

覆盖模块:dis(字节码反汇编器)。

真实测试项:
  - `dis.dis(func)` 真把 RESUME/LOAD_FAST/LOAD_CONST/BINARY_OP/RETURN_VALUE 打到 stdout
  - `dis.get_instructions(func)` 真产出按 offset 递增的指令序列
  - `Instruction.argval` / `argrepr` 真解析出常量值、形参名与运算符
  - `dis.opname` / `dis.opmap` 对全部 opcode 真双向一致
  - `dis.HAVE_ARGUMENT` 阈值真标出带参数的 opcode(`dis.hasarg` 自 3.11 起已移除)
  - `dis.hasname` / `hasconst` / `hasjrel` / `hasjabs` / `haslocal` / `hasfree` 真区分 opcode 类别
  - `dis.stack_effect` 真算出每条指令的栈增减
  - `dis.stack_effect` 缺 oparg 或多传 oparg 时真抛 ValueError
  - `dis.stack_effect(..., jump=True)` 真给出跳转指令的栈效果
  - `dis.Bytecode(func)` 迭代结果真与 `dis.get_instructions` 一致
  - `code.co_code` 真字节与指令 offset/opcode 一一对应
  - `dis.findlinestarts` 真给出 (offset, lineno) 行首映射
  - `dis.findlabels` 真找出全部跳转目标 offset
  - `Instruction.positions` 真带行列信息
  - `dis.show_code` 真打印 code object 元信息
  - `dis.dis(cls)` 真逐个方法反汇编
  - `dis.get_instructions(..., show_caches=True)` 真暴露内联缓存条目
  - `dis.COMPILER_FLAG_NAMES` 真映射 code flags 位
"""

import dis
import io
from contextlib import redirect_stdout

import pytest


def _add_one(x):
    return x + 1


def _sum_even_odd(n):
    total = 0
    for i in range(n):
        if i % 2 == 0:
            total += i
        else:
            total -= i
    return total


class _Sample:
    def method_a(self):
        return 1

    def method_b(self):
        return 2


class TestDisOutput:
    def test_dis_dis_prints_real_instruction_lines_to_stdout(self):
        """`dis.dis(_add_one)` 真把指令逐条打到 stdout,含 BINARY_OP 的 '+' 与常量 1。"""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            dis.dis(_add_one)
        output = buffer.getvalue()
        assert "RESUME" in output
        assert "LOAD_FAST" in output
        assert "LOAD_CONST" in output
        assert "BINARY_OP" in output
        assert "RETURN_VALUE" in output
        assert "(+)" in output
        assert "(1)" in output

    def test_dis_get_instructions_returns_real_opcode_sequence(self):
        """`dis.get_instructions` 真产出 RESUME→LOAD_FAST→LOAD_CONST→BINARY_OP→RETURN_VALUE 序列。"""
        instructions = list(dis.get_instructions(_add_one))
        assert [item.opname for item in instructions] == [
            "RESUME",
            "LOAD_FAST",
            "LOAD_CONST",
            "BINARY_OP",
            "RETURN_VALUE",
        ]
        assert [item.offset for item in instructions] == [0, 2, 4, 6, 10]

    def test_dis_instruction_argval_resolves_constants_and_names(self):
        """`Instruction.argval` 真取到常量 1 与形参名 x,`argrepr` 真渲染成 '1' 与 '+'。"""
        by_opname = {item.opname: item for item in dis.get_instructions(_add_one)}
        assert by_opname["LOAD_CONST"].argval == 1
        assert by_opname["LOAD_CONST"].argrepr == "1"
        assert by_opname["LOAD_FAST"].argval == "x"
        assert by_opname["LOAD_FAST"].argrepr == "x"
        assert by_opname["BINARY_OP"].argrepr == "+"
        assert by_opname["RETURN_VALUE"].argval is None

    def test_dis_opname_opmap_round_trip_covers_all_opcodes(self):
        """`dis.opname[dis.opmap[名]]` 对每个 opcode 真还原出原名,opname 表长度为 256。"""
        assert len(dis.opname) == 256
        for name, value in dis.opmap.items():
            assert dis.opname[value] == name
        assert dis.opmap["LOAD_CONST"] == 100
        assert dis.opname[dis.opmap["LOAD_CONST"]] == "LOAD_CONST"
        assert dis.opname[0] == "CACHE"


class TestDisOpcodeMetadata:
    def test_dis_have_argument_threshold_marks_argument_opcodes(self):
        """带参数的 opcode 真由 `dis.HAVE_ARGUMENT`(=90)阈值界定,`dis.hasarg` 在 3.11 已移除。"""
        assert dis.HAVE_ARGUMENT == 90
        assert dis.opmap["LOAD_CONST"] >= dis.HAVE_ARGUMENT
        assert dis.opmap["STORE_NAME"] >= dis.HAVE_ARGUMENT
        assert dis.opmap["RESUME"] >= dis.HAVE_ARGUMENT
        assert dis.opmap["NOP"] < dis.HAVE_ARGUMENT
        assert not hasattr(dis, "hasarg")

    def test_dis_opcode_flag_tables_classify_name_const_and_jump_opcodes(self):
        """`dis.hasname/hasconst/hasjrel/haslocal/hasfree` 真以 opcode 数值列出该类别指令。"""
        assert dis.opmap["STORE_NAME"] in dis.hasname
        assert dis.opmap["LOAD_CONST"] not in dis.hasname
        assert dis.opmap["LOAD_CONST"] in dis.hasconst
        assert dis.opmap["STORE_NAME"] not in dis.hasconst
        assert dis.opmap["FOR_ITER"] in dis.hasjrel
        assert dis.opmap["JUMP_FORWARD"] in dis.hasjrel
        assert dis.opmap["LOAD_FAST"] in dis.haslocal
        assert dis.opmap["LOAD_DEREF"] in dis.hasfree
        assert dis.opmap["COMPARE_OP"] in dis.hascompare
        assert dis.hasjabs == []

    def test_dis_compiler_flag_names_map_code_flag_bits(self):
        """`dis.COMPILER_FLAG_NAMES` 真把 code flags 位映射成 OPTIMIZED/GENERATOR/VARKEYWORDS 等名字。"""
        assert dis.COMPILER_FLAG_NAMES[1] == "OPTIMIZED"
        assert dis.COMPILER_FLAG_NAMES[8] == "VARKEYWORDS"
        assert dis.COMPILER_FLAG_NAMES[32] == "GENERATOR"
        flags_text = dis.pretty_flags(_add_one.__code__.co_flags)
        assert "OPTIMIZED" in flags_text
        assert "NEWLOCALS" in flags_text

    def test_dis_stack_effect_reports_stack_delta_per_opcode(self):
        """`dis.stack_effect` 真算出栈增减:BINARY_OP -1、LOAD_CONST +1、RETURN_VALUE -1、POP_TOP -1、NOP 0。"""
        assert dis.stack_effect(dis.opmap["BINARY_OP"], 0) == -1
        assert dis.stack_effect(dis.opmap["LOAD_CONST"], 0) == 1
        assert dis.stack_effect(dis.opmap["RETURN_VALUE"]) == -1
        assert dis.stack_effect(dis.opmap["POP_TOP"]) == -1
        assert dis.stack_effect(dis.opmap["NOP"]) == 0
        assert dis.stack_effect(dis.opmap["PUSH_NULL"]) == 1

    def test_dis_stack_effect_rejects_missing_or_extra_oparg(self):
        """带参 opcode 缺 oparg、无参 opcode 多传 oparg 时,`dis.stack_effect` 真抛 ValueError。"""
        with pytest.raises(ValueError, match="requires oparg"):
            dis.stack_effect(dis.opmap["LOAD_CONST"])
        with pytest.raises(ValueError, match="does not permit oparg"):
            dis.stack_effect(dis.opmap["RETURN_VALUE"], 0)

    def test_dis_stack_effect_jump_mode_reports_jump_opcode_effect(self):
        """`jump=True` 时跳转指令栈效果为 0,普通算术指令仍为 -1。"""
        assert dis.stack_effect(dis.opmap["JUMP_FORWARD"], 0, jump=True) == 0
        assert dis.stack_effect(dis.opmap["JUMP_BACKWARD"], 0, jump=True) == 0
        assert dis.stack_effect(dis.opmap["BINARY_OP"], 0, jump=True) == -1


class TestDisBytecodeLayout:
    def test_dis_bytecode_iteration_equals_get_instructions(self):
        """`dis.Bytecode` 迭代出的指令真与 `dis.get_instructions` 完全一致。"""
        from_bytecode = list(dis.Bytecode(_add_one))
        from_instructions = list(dis.get_instructions(_add_one))
        assert from_bytecode == from_instructions
        assert [item.offset for item in from_bytecode] == [0, 2, 4, 6, 10]

    def test_dis_code_bytes_match_instruction_offsets(self):
        """`code.co_code` 真字节与指令一一对应:offset 0 是 RESUME、4 是 LOAD_CONST、10 是 RETURN_VALUE。"""
        raw = _add_one.__code__.co_code
        assert len(raw) == 12
        assert raw[0] == dis.opmap["RESUME"]
        assert raw[1] == 0
        assert raw[2] == dis.opmap["LOAD_FAST"]
        assert raw[4] == dis.opmap["LOAD_CONST"]
        assert raw[5] == 1
        assert raw[6] == dis.opmap["BINARY_OP"]
        assert raw[10] == dis.opmap["RETURN_VALUE"]

    def test_dis_findlinestarts_maps_offsets_to_source_lines(self):
        """`dis.findlinestarts` 真给出 (offset, lineno):def 行在 offset 0,return 行在 offset 2。"""
        code_obj = _add_one.__code__
        starts = list(dis.findlinestarts(code_obj))
        assert [offset for offset, _ in starts] == [0, 2]
        assert [lineno for _, lineno in starts] == [
            code_obj.co_firstlineno,
            code_obj.co_firstlineno + 1,
        ]

    def test_dis_findlabels_matches_jump_target_offsets(self):
        """`dis.findlabels` 真找出全部跳转目标 offset,且与 `is_jump_target` 集合完全一致。"""
        code_obj = _sum_even_odd.__code__
        labels = sorted(dis.findlabels(code_obj.co_code))
        targets = sorted(
            item.offset
            for item in dis.get_instructions(_sum_even_odd)
            if item.is_jump_target
        )
        assert labels == targets
        assert len(labels) == 3
        instruction_offsets = {item.offset for item in dis.get_instructions(_sum_even_odd)}
        assert set(labels) <= instruction_offsets

    def test_dis_instruction_positions_carry_line_and_column(self):
        """`Instruction.positions` 真带行列:return 语句在 def+1 行、列 4-16,形参 x 在列 11-12。"""
        by_opname = {item.opname: item for item in dis.get_instructions(_add_one)}
        return_position = by_opname["RETURN_VALUE"].positions
        assert return_position.lineno == _add_one.__code__.co_firstlineno + 1
        assert return_position.end_lineno == _add_one.__code__.co_firstlineno + 1
        assert return_position.col_offset == 4
        assert return_position.end_col_offset == 16
        load_position = by_opname["LOAD_FAST"].positions
        assert load_position.col_offset == 11
        assert load_position.end_col_offset == 12

    def test_dis_get_instructions_show_caches_exposes_inline_caches(self):
        """`show_caches=True` 真多吐出内联 CACHE 条目,新增条目的 opname 全为 CACHE。"""
        plain = list(dis.get_instructions(_sum_even_odd))
        cached = list(dis.get_instructions(_sum_even_odd, show_caches=True))
        assert len(cached) > len(plain)
        plain_names = {item.opname for item in plain}
        extra_names = {item.opname for item in cached} - plain_names
        assert extra_names == {"CACHE"}


class TestDisCodeObjectView:
    def test_dis_show_code_prints_code_object_metadata(self):
        """`dis.show_code` 真打印 name/参数个数/常量表/局部变量名。"""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            dis.show_code(_add_one)
        output = buffer.getvalue()
        assert "Name:" in output
        assert "_add_one" in output
        assert "Argument count:    1" in output
        assert "Constants:" in output
        assert "Variable names:" in output
        assert "Flags:             OPTIMIZED, NEWLOCALS" in output

    def test_dis_dis_of_class_lists_each_method(self):
        """`dis.dis(cls)` 真逐个方法反汇编,输出含 'Disassembly of method_a:' 与 method_b。"""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            dis.dis(_Sample)
        output = buffer.getvalue()
        assert "Disassembly of method_a:" in output
        assert "Disassembly of method_b:" in output
        assert "RETURN_VALUE" in output
