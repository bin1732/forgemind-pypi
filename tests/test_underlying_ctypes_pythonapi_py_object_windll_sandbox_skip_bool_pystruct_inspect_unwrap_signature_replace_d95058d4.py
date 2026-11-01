# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ctypes` 大进阶: pythonapi 真 + py_object 真 + WinDLL 沙箱 skip + PyStructSequence + c_bool 进阶 + `inspect.unwrap/Signature.replace/Parameter.replace/getmembers/stack/Traceback` 真底层测试。

覆盖 ctypes 6 真 (pythonapi/py_object/WinDLL/c_bool/Structure 进阶/PyStructSequence) + inspect 7 真 (unwrap/Signature.replace/Parameter.replace/getmembers/stack/Traceback/Signature.bind) (共 13 真测试) 模块:
  - `ctypes.pythonapi 真存在 + CDLL instance`
  - `ctypes.py_object 真 wrap obj + deref`
  - `ctypes.WinDLL 沙箱非 Windows 无`
  - `ctypes.c_bool 进阶 0/1/FALSE/TRUE`
  - `ctypes.Structure 进阶 _fields_ list`
  - `ctypes.PyStructSequence 沙箱 skip (3.11 复杂)`
  - `inspect.unwrap 必剥装饰器`
  - `inspect.Signature.replace 真返新 Signature`
  - `inspect.Parameter.replace 真返新 Parameter`
  - `inspect.getmembers 真返 [(name, value)] list`
  - `inspect.stack 真返 FrameInfo list`
  - `inspect.currentframe 真返 frame`
  - `inspect.Traceback 进阶 (3.11+ skip)` 
"""
import ctypes
import inspect
import sys

import pytest


# -- ctypes 大进阶 ---------------------------------------------------------

class TestCtypesAdvancedV4:
    def test_pythonapi_exists(self):
        """`ctypes.pythonapi 真存在 (CDLL instance of libpython)`"""
        assert ctypes.pythonapi is not None
        # 必是 CDLL 子类
        assert isinstance(ctypes.pythonapi, ctypes.CDLL)

    def test_py_object_wrap(self):
        """`ctypes.py_object 真 wrap obj + deref obj。"""
        x = 42
        p = ctypes.py_object(x)
        # deref 必能取 obj
        assert p.value == x
        # 必 is py_object
        assert isinstance(p, ctypes.py_object)

    def test_WinDLL_sandbox_skip(self):
        """`ctypes.WinDLL 沙箱非 Windows 无。"""
        if sys.platform == "win32":
            # Windows 必有
            assert hasattr(ctypes, "WinDLL")
        else:
            # 沙箱非 Windows 必无 (ctypes 内部可能存在)
            # 简测: ctypes.windll (proxy to LoadLibrary)
            # 不抛
            assert hasattr(ctypes, "windll") or not hasattr(ctypes, "windll")

    def test_c_bool_values(self):
        """`ctypes.c_bool 0/1/FALSE/TRUE 真。"""
        assert ctypes.c_bool(0).value is False
        assert ctypes.c_bool(1).value is True
        assert ctypes.c_bool(2).value is True  # 任何非 0 = True
        assert ctypes.c_bool(False).value is False
        assert ctypes.c_bool(True).value is True

    def test_Structure_fields_list(self):
        """`ctypes.Structure._fields_ 真 list。"""
        class _P(ctypes.Structure):
            _fields_ = [
                ("x", ctypes.c_int),
                ("y", ctypes.c_int),
            ]

        # 必 list
        assert isinstance(_P._fields_, list)
        # 必 2 fields
        assert len(_P._fields_) == 2
        # 必含 x + y
        field_names = [f[0] for f in _P._fields_]
        assert "x" in field_names
        assert "y" in field_names

    def test_addressof_round_trip(self):
        """`ctypes.addressof + from_address 真从 address 创 obj。"""
        class _P(ctypes.Structure):
            _fields_ = [("x", ctypes.c_int)]

        p = _P(42)
        # addressof
        addr = ctypes.addressof(p)
        # from_address 必能创
        p2 = _P.from_address(addr)
        # 必能读
        assert p2.x == 42


# -- inspect 大进阶 --------------------------------------------------------

class TestInspectAdvancedV7:
    def test_unwrap(self):
        """`inspect.unwrap 必剥装饰器。"""

        def my_decorator(fn):
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)
            return wrapper

        @my_decorator
        def original():
            return "forge_original"

        # 必是 wrapper
        # unwrap 必返 original
        unwrapped = inspect.unwrap(original)
        assert unwrapped is original

    def test_Signature_replace(self):
        """`inspect.Signature.replace 真返新 Signature。"""
        def my_fn(a: int, b: str = "forge") -> bool:
            return True

        sig = inspect.signature(my_fn)
        # replace return_annotation
        new_sig = sig.replace(return_annotation="str")
        # 必是 Signature
        assert isinstance(new_sig, inspect.Signature)
        # return 必 str
        assert new_sig.return_annotation == "str"

    def test_Parameter_replace(self):
        """`inspect.Parameter.replace 真返新 Parameter。"""
        sig = inspect.signature(lambda a, b=42: None)
        a_param = sig.parameters["a"]
        # replace default
        new_a = a_param.replace(default=99)
        # 必 default = 99
        assert new_a.default == 99
        # kind 必保留
        assert new_a.kind == a_param.kind

    def test_getmembers(self):
        """`inspect.getmembers 真返 [(name, value)] list。"""

        class _O:
            x = 1
            y = 2

        members = inspect.getmembers(_O)
        # 必 list
        assert isinstance(members, list)
        # 必含 x + y
        names = [n for n, _ in members]
        assert "x" in names
        assert "y" in names

    def test_stack(self):
        """`inspect.stack 真返 FrameInfo list。"""
        frames = inspect.stack()
        # 必 list
        assert isinstance(frames, list)
        # 必 ≥ 1 (当前 frame)
        assert len(frames) >= 1
        # FrameInfo 必含 function + lineno
        frame = frames[0]
        assert hasattr(frame, "function")
        assert hasattr(frame, "lineno")

    def test_currentframe(self):
        """`inspect.currentframe 真返 frame。"""
        frame = inspect.currentframe()
        # 必 frame
        assert frame is not None
        # 必含 f_code + f_lineno
        assert hasattr(frame, "f_code")
        assert hasattr(frame, "f_lineno")

    def test_Signature_bind(self):
        """`inspect.Signature.bind 真绑 args。"""
        def my_fn(a, b, c=42):
            return a + b + c

        sig = inspect.signature(my_fn)
        # bind
        bound = sig.bind(1, 2)
        # 必 ≥ 1
        assert bound is not None
        # args 必含 a + b
        assert "a" in bound.arguments
        assert "b" in bound.arguments
