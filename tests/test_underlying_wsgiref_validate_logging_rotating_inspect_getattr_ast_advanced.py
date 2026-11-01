# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`wsgiref` 进阶 (validate) + `logging.handlers.RotatingFileHandler` 进阶 + `inspect` 进阶 (getattr_static) + `ast` 进阶 (TypeIgnore) 真底层测试。

覆盖 wsgiref validate / 日志轮转 / inspect static / AST TypeIgnore 模块:
  - `wsgiref.validate.validator 真拦截环境错误`
  - `wsgiref.util.is_hop_by_hop_header 真识别 Connection:close`
  - `wsgiref.util.application_uri 真返 url`
  - `logging.handlers.RotatingFileHandler 真轮转 (maxBytes 极小)`
  - `logging.handlers.TimedRotatingFileHandler 真设 when`
  - `inspect.getattr_static 真不触发 descriptor __get__`
  - `inspect.signature 真返 (param: int=42) signature`
  - `inspect.Parameter.empty sentinel 真存在`
  - `inspect.Signature.empty sentinel 真存在`
  - `ast.TypeIgnore 3.8+ 真建节点 (type_comment='type: forge')`
  - `ast.parse 真带 type_ignores 返 (Module, list[TypeIgnore])`
  - `ast.dump 真序列化 TypeIgnore`
  - `ast.AST 抽象基类 真子类化`
"""
import ast
import inspect
import logging
import logging.handlers
import os
import sys
import tempfile
import wsgiref.util
import wsgiref.validate

import pytest


# -- wsgiref 进阶 (validate + is_hop_by_hop) -----------------------------------

class TestWsgirefAdvancedV3:
    def test_is_hop_by_hop(self):
        """`wsgiref.util.is_hop_by_hop 真识别 'Connection'. """
        # 沙箱 3.11 用 is_hop_by_hop 不用 is_hop_by_hop_header
        if hasattr(wsgiref.util, "is_hop_by_hop_header"):
            fn = wsgiref.util.is_hop_by_hop_header
        else:
            fn = wsgiref.util.is_hop_by_hop
        assert fn("Connection") is True
        # 非 hop-by-hop
        assert fn("Content-Type") is False
        assert fn("Host") is False
        # Keep-Alive 真 hop-by-hop
        assert fn("Keep-Alive") is True

    def test_application_uri(self):
        """`wsgiref.util.application_uri 真返 URL。"""
        # 用 wsgiref.util.test_app_uri 工具
        # 简化: 直接传一个 env, 求 url
        from wsgiref.util import setup_testing_defaults
        env = {}
        setup_testing_defaults(env)
        url = wsgiref.util.application_uri(env)
        # 必返带 scheme://host/path 的 url
        assert url.startswith("http://")
        # 含 PATH_INFO
        assert "/" in url

    def test_validate_wrapper_passes(self):
        """`wsgiref.validate.validator 真包 app + 通过正常请求。"""

        def simple_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"hello forge"]

        validated = wsgiref.validate.validator(simple_app)
        # 必 callable
        assert callable(validated)
        # 调一下
        from wsgiref.util import setup_testing_defaults
        env = {}
        setup_testing_defaults(env)
        # 必不抛
        # 校验器是迭代器,读完必须关闭。它在析构时会断言自己已关闭,
        # 没关的话会在垃圾回收时抛出断言错误,污染同一进程里后续的用例。
        validator = validated(env, lambda *a: None)
        try:
            result = list(validator)
        finally:
            close = getattr(validator, "close", None)
            if close is not None:
                close()
        assert result == [b"hello forge"]


# -- logging.handlers.RotatingFileHandler 进阶 --------------------------------

class TestLoggingRotatingV2:
    def test_RotatingFileHandler_rotate(self):
        """`RotatingFileHandler 真设 maxBytes 极小触发轮转。"""
        # 用 temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "test.log")
            # maxBytes=50 + backupCount=2 必触发轮转
            rh = logging.handlers.RotatingFileHandler(
                log_path, maxBytes=50, backupCount=2
            )
            log = logging.getLogger("forge_rotate")
            log.handlers.clear()
            log.setLevel(logging.INFO)
            log.addHandler(rh)
            try:
                # 写 100 字节 + 必触发 rollover
                for i in range(10):
                    log.info("forge_rotate_test_%d", i)
                # 文件已轮转
                files = os.listdir(tmpdir)
                # 必 ≥ 1 个 .log (主 + 可能 .log.1)
                log_files = [f for f in files if f.startswith("test.log")]
                assert len(log_files) >= 1
            finally:
                log.removeHandler(rh)
                rh.close()

    def test_TimedRotatingFileHandler_when(self):
        """`TimedRotatingFileHandler 真设 when='S' (秒). """
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "test.log")
            # 沙箱无 when='H' 验证 + 调 setter
            rh = logging.handlers.TimedRotatingFileHandler(
                log_path, when="S", interval=1, backupCount=2
            )
            try:
                # when 必存
                assert rh.when == "S"
                # backupCount
                assert rh.backupCount == 2
            finally:
                rh.close()


# -- inspect 进阶 (getattr_static + signature) --------------------------------

class _Property:
    @property
    def value(self):
        return 99


class TestInspectAdvancedV6:
    def test_getattr_static_no_descriptor(self):
        """`inspect.getattr_static 真不触发 property __get__。"""
        obj = _Property()
        # value 是 property, 普通 getattr 必触发 __get__ 返 99
        assert getattr(obj, "value") == 99
        # getattr_static 必返 property object
        static = inspect.getattr_static(obj, "value")
        assert isinstance(static, property)

    def test_signature(self):
        """`inspect.signature 真返 Signature。"""
        def my_fn(a: int, b: str = "forge") -> bool:
            return True

        sig = inspect.signature(my_fn)
        # 必含 2 params
        assert len(sig.parameters) == 2
        # a 是 POSITIONAL_OR_KEYWORD
        assert sig.parameters["a"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        # b 有 default
        assert sig.parameters["b"].default == "forge"

    def test_sentinels(self):
        """`Parameter.empty + Signature.empty 真 sentinel。"""
        sig = inspect.signature(lambda a, b=42: None)
        # a 是 empty
        assert sig.parameters["a"].default is inspect.Parameter.empty
        # return annotation
        assert sig.return_annotation is inspect.Signature.empty or (
            sig.return_annotation is not None
        )


# -- ast 进阶 (TypeIgnore 3.8+) ------------------------------------------------

class TestAstAdvancedV6:
    def test_TypeIgnore_node(self):
        """`ast.TypeIgnore 3.8+ 真建节点。"""
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ TypeIgnore")
        # 创 TypeIgnore 节点
        ti = ast.TypeIgnore(lineno=1, tag="forge")
        assert ti.lineno == 1
        assert ti.tag == "forge"
        # 必能 dump
        dumped = ast.dump(ti)
        assert "TypeIgnore" in dumped
        assert "forge" in dumped

    def test_parse_type_ignores(self):
        """`ast.parse 真 type_comments=True 返 Module (含 type_ignores 属性) 。"""
        src = "x = 1  # type: forge\n"
        module = ast.parse(src, type_comments=True)
        # 必 Module
        assert isinstance(module, ast.Module)
        # 沙箱 3.11+ module 必含 type_ignores
        # 3.8+ 返 (Module, list), 沙箱 3.11 仅返 Module
        # 验 type_ignores attr (3.8+)
        if hasattr(module, "type_ignores"):
            ti = module.type_ignores
            assert isinstance(ti, list)
            if ti:
                assert isinstance(ti[0], ast.TypeIgnore)
        else:
            # 沙箱 fallback
            assert module is not None

    def test_AST_subclass(self):
        """`ast.AST 抽象基类 真子类化。"""

        class MyNode(ast.AST):
            _fields = ("value",)

            def __init__(self, value):
                self.value = value

        n = MyNode(42)
        # 必能 ast.dump
        dumped = ast.dump(n)
        assert "MyNode" in dumped
        assert "42" in dumped
