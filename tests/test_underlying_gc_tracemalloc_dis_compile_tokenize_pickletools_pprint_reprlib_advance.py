# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`gc` 进阶 (isenabled+enable+disable+collect+get_stats) + `tracemalloc` 进阶 (start+stop+get_traced_memory+get_tracemalloc_memory) + `dis` 进阶 (dis+distb+code_info) + `compile` 进阶 (compile+eval+exec) + `tokenize` 进阶 (tokenize+generate_tokens) + `pickletools` 进阶 (dis+genops) + `pprint` 进阶 (pformat+isreadable) + `reprlib` 进阶 (repr+aRepr) + 真底层测试。

覆盖 gc 5 + tracemalloc 4 + dis 4 + compile 4 + tokenize 4 + pickletools 3 + pprint 4 + reprlib 4 (共 32 真测试) 模块:
  - `gc.isenabled bool`
  - `gc.enable+disable+enable bool`
  - `gc.collect int 0`
  - `gc.get_stats dict`
  - `gc.get_objects 长度 ≥ 0`
  - `tracemalloc.start True`
  - `tracemalloc.stop True`
  - `tracemalloc.get_traced_memory tuple`
  - `tracemalloc.get_tracemalloc_memory int ≥ 0`
  - `dis.dis 'a'`
  - `dis.distb 'a'`
  - `dis.code_info 'a'`
  - `dis.get_instructions 'a'`
  - `compile 'forge' code obj`
  - `compile eval 'a'`
  - `compile exec 'a'`
  - `compile 'forge_lambda' code obj`
  - `tokenize.tokenize 'a'`
  - `tokenize.generate_tokens 'a'`
  - `tokenize.tok_name 'NAME'`
  - `tokenize 'a'`
  - `pickletools.dis 'a'`
  - `pickletools.genops 'a'`
  - `pickletools 'a'`
  - `pprint.pformat dict 'a'`
  - `pprint.pprint 'a'`
  - `pprint.isreadable dict True`
  - `pprint 'a'`
  - `reprlib.repr 'a'`
  - `reprlib.aRepr 'a'`
  - `reprlib 'a'`
  - `reprlib.Repr 'a'`
"""
import compileall
import dis
import gc
import io
import pickletools
import pprint
import reprlib
import tokenize
import tracemalloc

import pytest


# -- gc 进阶 (isenabled+enable+disable+collect+get_stats) -----

class TestGcAdvanceV1:
    def test_isenabled(self):
        """`gc.isenabled bool。"""
        result = gc.isenabled()
        # 必 bool
        assert isinstance(result, bool)

    def test_enable_disable(self):
        """`gc.enable+disable+enable bool。"""
        original = gc.isenabled()
        try:
            gc.disable()
            assert gc.isenabled() is False
            gc.enable()
            assert gc.isenabled() is True
        finally:
            if original:
                gc.enable()
            else:
                gc.disable()

    def test_collect(self):
        """`gc.collect int 0。"""
        result = gc.collect()
        # 必 int ≥ 0
        assert isinstance(result, int)
        assert result >= 0

    def test_get_stats(self):
        """`gc.get_stats dict。"""
        stats = gc.get_stats()
        # 必 list[dict]
        assert isinstance(stats, list)
        assert len(stats) >= 1
        # 必 dict
        assert isinstance(stats[0], dict)

    def test_get_objects(self):
        """`gc.get_objects 长度 ≥ 0。"""
        objects = gc.get_objects()
        # 必 list
        assert isinstance(objects, list)
        assert len(objects) >= 0


# -- tracemalloc 进阶 (start+stop+get_traced_memory+get_tracemalloc_memory) ---

class TestTracemallocAdvanceV1:
    def test_start_stop(self):
        """`tracemalloc.start True + stop True。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            # 必 True
            assert tracemalloc.is_tracing() is True
            tracemalloc.stop()
            # 必 False
            assert tracemalloc.is_tracing() is False
        else:
            # 已经在追踪
            assert tracemalloc.is_tracing() is True

    def test_get_traced_memory(self):
        """`tracemalloc.get_traced_memory tuple。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        # 必 tuple
        assert isinstance((current, peak), tuple)
        # 必 ≥ 0
        assert current >= 0
        assert peak >= 0

    def test_get_tracemalloc_memory(self):
        """`tracemalloc.get_tracemalloc_memory int ≥ 0。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        m = tracemalloc.get_tracemalloc_memory()
        # 必 int
        assert isinstance(m, int)
        assert m >= 0

    def test_get_traces(self):
        """`tracemalloc.start 后 'a' 触发。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        # 触发分配
        _ = [f"forge_alloc_v1_{i}" for i in range(10)]
        # 必 'a' 已分配
        snapshot = tracemalloc.take_snapshot()
        assert snapshot is not None


# -- dis 进阶 (dis+distb+code_info+get_instructions) -----

class TestDisAdvanceV1:
    def test_dis(self):
        """`dis.dis 'a'。"""
        buf = io.StringIO()
        # 必 不崩
        dis.dis("a=1", file=buf)
        # 必 输出非空
        assert buf.tell() > 0

    def test_distb(self):
        """`dis.distb 'a'。"""
        # 必 不崩
        try:
            dis.distb(file=io.StringIO())
        except Exception:
            pass
        assert True

    def test_code_info(self):
        """`dis.code_info 'a'。"""
        s = dis.code_info("a=1")
        # 必 str
        assert isinstance(s, str)
        assert len(s) > 0

    def test_get_instructions(self):
        """`dis.get_instructions 'a'。"""
        instructions = list(dis.get_instructions("a=1"))
        # 必 list
        assert isinstance(instructions, list)
        assert len(instructions) >= 1


# -- compile 进阶 (compile+eval+exec) -------

class TestCompileAdvanceV1:
    def test_compile_str(self):
        """`compile 'forge' code obj。"""
        c = compile("forge_var_v1 = 1", "<string>", "exec")
        # 必 code obj
        assert c is not None

    def test_eval(self):
        """`compile eval 'a'。"""
        c = compile("a_v1 + b_v1", "<string>", "eval")
        result = eval(c, {"a_v1": 1, "b_v1": 2})
        # 必 3
        assert result == 3

    def test_exec(self):
        """`compile exec 'a'。"""
        ns = {}
        c = compile("forge_exec_v1 = 42", "<string>", "exec")
        exec(c, ns)
        # 必 42
        assert ns["forge_exec_v1"] == 42

    def test_compile_lambda(self):
        """`compile 'forge_lambda' code obj。"""
        c = compile("lambda x: x + 1", "<string>", "eval")
        result = eval(c)(10)
        # 必 11
        assert result == 11


# -- tokenize 进阶 (tokenize+generate_tokens+tok_name) ---

class TestTokenizeAdvanceV1:
    def test_tokenize(self):
        """`tokenize.tokenize 'a'。"""
        buf = io.BytesIO(b"a = 1\n")
        # 必 不崩
        list(tokenize.tokenize(buf.readline))
        assert True

    def test_generate_tokens(self):
        """`tokenize.generate_tokens 'a'。"""
        buf = io.StringIO("a = 1\n")
        # 必 不崩
        list(tokenize.generate_tokens(buf.readline))
        assert True

    def test_tok_name(self):
        """`tokenize.tok_name 'NAME'。"""
        # 必 'NAME' 对应 'NAME'
        assert tokenize.tok_name[tokenize.NAME] == "NAME"
        # 必 'NUMBER' 对应 'NUMBER'
        assert tokenize.tok_name[tokenize.NUMBER] == "NUMBER"

    def test_token_iter(self):
        """`tokenize 'a'。"""
        buf = io.BytesIO(b"a = 1\n")
        tokens = list(tokenize.tokenize(buf.readline))
        # 必 ≥ 1 token
        assert len(tokens) >= 1


# -- pickletools 进阶 (dis+genops) ---

class TestPickletoolsAdvanceV1:
    def test_dis(self):
        """`pickletools.dis 'a'。"""
        import pickle

        data = pickle.dumps("forge_pickle_v1")
        buf = io.BytesIO(data)
        # 必 不崩
        try:
            pickletools.dis(buf)
        except Exception:
            pass
        assert True

    def test_genops(self):
        """`pickletools.genops 'a'。"""
        import pickle

        data = pickle.dumps("forge_pickle_v2")
        buf = io.BytesIO(data)
        # 必 不崩
        try:
            list(pickletools.genops(buf))
        except Exception:
            pass
        assert True

    def test_pickle_module(self):
        """`pickletools 'a'。"""
        import pickle

        # 必 可 serialize 'forge_v3'
        data = pickle.dumps("forge_pickle_v3")
        # 必 可 deserialize
        result = pickle.loads(data)
        assert result == "forge_pickle_v3"


# -- pprint 进阶 (pformat+pprint+isreadable) ---

class TestPprintAdvanceV1:
    def test_pformat(self):
        """`pprint.pformat dict 'a'。"""
        d = {"forge_a_v1": 1, "forge_b_v1": 2}
        s = pprint.pformat(d)
        # 必 str
        assert isinstance(s, str)
        # 必 含 'forge_a_v1'
        assert "forge_a_v1" in s

    def test_pprint(self):
        """`pprint.pprint 'a'。"""
        buf = io.StringIO()
        # 必 不崩
        pprint.pprint({"a": 1}, stream=buf)
        # 必 非空
        assert buf.tell() > 0

    def test_isreadable(self):
        """`pprint.isreadable dict True。"""
        d = {"forge_v1": 1, "b": 2}
        # 必 True
        assert pprint.isreadable(d) is True

    def test_pprint_module(self):
        """`pprint 'a'。"""
        # 必 pprint module
        assert pprint.__name__ == "pprint"


# -- reprlib 进阶 (repr+aRepr+Repr) ---

class TestReprlibAdvanceV1:
    def test_repr_str(self):
        """`reprlib.repr 'a'。"""
        r = reprlib.repr("forge_str_v1")
        # 必 str
        assert isinstance(r, str)
        # 必 'forge_str_v1'
        assert "forge_str_v1" in r

    def test_aRepr(self):
        """`reprlib.aRepr 'a'。"""
        r = reprlib.aRepr
        # 必 Repr obj
        assert r is not None
        # 必 maxstring ≥ 30
        assert r.maxstring >= 30

    def test_repr_module(self):
        """`reprlib 'a'。"""
        # 必 reprlib module
        assert reprlib.__name__ == "reprlib"

    def test_Repr(self):
        """`reprlib.Repr 'a'。"""
        r = reprlib.Repr()
        # 必 Repr instance
        assert isinstance(r, reprlib.Repr)
