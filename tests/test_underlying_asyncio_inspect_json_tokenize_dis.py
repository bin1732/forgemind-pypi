# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 asyncio 真 (create_task 真 / shield 真) + 真 inspect 真 (getframeinfo 真 / currentframe) + 真 json 真 (dumps 真 中文 ensure_ascii=False) + 真 tokenize 真 (encoding name) + 真 traceback 真 (format_stack 真) + 真 dis 真 (stack_effect) + 真 platform 进阶.
全 stdlib, 零模拟。
"""
import asyncio
import inspect
import json
import tokenize
import traceback
import dis
import platform
import io
import pytest


# ======================== asyncio 进阶 ========================
def test_asyncio_create_task():
    """真 create_task 真"""
    async def main():
        async def task():
            return 42

        t = asyncio.create_task(task())
        result = await t
        assert result == 42

    asyncio.run(main())


def test_asyncio_shield_protect():
    """真 shield 真保护不被 cancel"""
    async def main():
        async def inner():
            return "inner done"

        # shield 包
        s = asyncio.shield(inner())
        try:
            result = await asyncio.wait_for(s, timeout=1.0)
            assert result == "inner done"
        except asyncio.TimeoutError:
            pytest.fail("shield shouldn't timeout")

    asyncio.run(main())


def test_asyncio_iscoroutine():
    """真 iscoroutine 真"""
    async def coro():
        return 1

    # coroutine object
    c = coro()
    try:
        assert asyncio.iscoroutine(c)
    finally:
        c.close()


# ======================== inspect 进阶 ========================
def test_inspect_getframeinfo():
    """真 getframeinfo 真"""
    # current frame
    frame = inspect.currentframe()
    info = inspect.getframeinfo(frame)
    # 必有 filename, lineno, function
    assert info.filename.endswith(".py")
    assert info.lineno > 0
    assert isinstance(info.function, str)


def test_inspect_signature_进阶():
    """真 signature 进阶"""
    def f(x: int, y: str = "default") -> bool:
        return True

    sig = inspect.signature(f)
    # parameters
    params = sig.parameters
    # x 必无 default
    assert "x" in params
    assert params["x"].default is inspect.Parameter.empty
    # y 必 default
    assert params["y"].default == "default"


# ======================== json 进阶 ========================
def test_json_dumps_unicode():
    """真 dumps 中文 ensure_ascii=False"""
    data = {"name": "中文", "value": 100}
    # 默认 ensure_ascii=True
    encoded = json.dumps(data, ensure_ascii=False)
    # 必含中文
    assert "中文" in encoded
    # round-trip
    decoded = json.loads(encoded)
    assert decoded == data


def test_json_separators():
    """真 separators 进阶"""
    data = {"a": 1, "b": 2}
    # default separators
    default = json.dumps(data)
    # no spaces
    no_space = json.dumps(data, separators=(",", ":"))
    # no_space 短
    assert len(no_space) < len(default)


def test_json_indent():
    """真 indent 真"""
    data = {"a": 1, "b": [1, 2, 3]}
    indented = json.dumps(data, indent=2)
    # 必有 \n
    assert "\n" in indented
    # round-trip
    decoded = json.loads(indented)
    assert decoded == data


# ======================== tokenize 进阶 ========================
def test_tokenize_encoding_name():
    """真 tokenize encoding name"""
    src = b"# -*- coding: utf-8 -*-\nx = 1\n"
    tokens = list(tokenize.tokenize(io.BytesIO(src).readline))
    # ENCODING token
    encoding_tokens = [t for t in tokens if t.type == tokenize.ENCODING]
    assert len(encoding_tokens) == 1
    assert encoding_tokens[0].string == "utf-8"


# ======================== traceback 进阶 ========================
def test_traceback_format_stack():
    """真 format_stack 真"""
    formatted = traceback.format_stack()
    # 必有 1+ 帧
    assert isinstance(formatted, list)
    assert len(formatted) >= 1
    # 必有 source code line
    assert all(isinstance(line, str) for line in formatted)


# ======================== dis 进阶 ========================
def test_dis_stack_effect():
    """真 stack_effect 真"""
    # 1 op: LOAD_FAST 0 → stack +1
    effect = dis.stack_effect(dis.opmap["LOAD_FAST"], 0)
    assert effect == 1
    # 1 op: STORE_FAST 0 → stack -1
    effect = dis.stack_effect(dis.opmap["STORE_FAST"], 0)
    assert effect == -1
    # 1 op: BINARY_OP / BINARY_ADD → stack -1
    effect = dis.stack_effect(dis.opmap["BINARY_OP"], 0)
    assert effect == -1


# ======================== platform 进阶 ========================
def test_platform_machine():
    """真 machine() 真"""
    m = platform.machine()
    # x86_64 / aarch64 / arm64
    assert isinstance(m, str)
    assert len(m) > 0


def test_platform_python_version_tuple():
    """真 python_version_tuple 真"""
    t = platform.python_version_tuple()
    # 3-tuple
    assert len(t) == 3
    assert t[0] == "3"
    assert int(t[1]) >= 11
    assert int(t[2]) >= 0
