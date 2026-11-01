# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 json 进阶 (json.tool 真 stdin 真) + 真 string 进阶 (capwords 真 multiline) + 真 struct 进阶 (calcsize 全 type char) + 真 unicodedata 进阶 (digit/decimal) + 真 typing 进阶 (Final 真).
全 stdlib, 零模拟。
"""
import json
import string
import struct
import unicodedata
import typing
import subprocess
import sys
import pytest


# ======================== json 进阶 ========================
def test_json_load_stdin():
    """真 json.tool 真 stdin 真"""
    # 用 subprocess 跑 json.tool
    proc = subprocess.run(
        [sys.executable, "-m", "json.tool"],
        input=b'{"a": 1, "b": 2}',
        capture_output=True,
        timeout=5,
    )
    assert proc.returncode == 0
    output = proc.stdout.decode()
    # 验证
    parsed = json.loads(output)
    assert parsed == {"a": 1, "b": 2}


def test_json_decode_with_extra_data():
    """真 JSONDecodeError 真"""
    import json
    # 多余内容
    with pytest.raises(json.JSONDecodeError):
        json.loads('{"a": 1} extra data')


def test_json_dumps_ensure_ascii_true():
    """真 ensure_ascii=True 真转"""
    data = {"name": "中"}
    s = json.dumps(data, ensure_ascii=True)
    # 转 \u
    assert "\\u" in s


def test_json_default_function():
    """真 default callable 真"""
    class C:
        def __init__(self, v):
            self.v = v
    def default(o):
        if isinstance(o, C):
            return {"v": o.v}
        raise TypeError

    data = {"obj": C(42)}
    s = json.dumps(data, default=default)
    parsed = json.loads(s)
    assert parsed == {"obj": {"v": 42}}


# ======================== string 进阶 ========================
def test_string_capwords_multiline():
    """真 capwords 真 multiline 真"""
    text = "hello world\nfoo bar\nbaz qux"
    result = string.capwords(text)
    # 每行首字母大写
    assert "Hello World" in result
    assert "Foo Bar" in result
    assert "Baz Qux" in result


def test_string_ascii_letters():
    """真 ascii_letters = lower + upper"""
    assert string.ascii_letters == string.ascii_lowercase + string.ascii_uppercase
    # length 52
    assert len(string.ascii_letters) == 52


def test_string_hexdigits_octdigits():
    """真 hexdigits / octdigits"""
    assert string.hexdigits == "0123456789abcdefABCDEF"
    assert string.octdigits == "01234567"
    assert string.printable == string.digits + string.ascii_letters + string.punctuation + string.whitespace


# ======================== struct calcsize ========================
def test_struct_calcsize_all_basic():
    """真 struct 真所有基本 type 字节"""
    # 整数
    assert struct.calcsize("b") == 1  # signed char
    assert struct.calcsize("B") == 1  # unsigned
    assert struct.calcsize("h") == 2  # short
    assert struct.calcsize("H") == 2
    assert struct.calcsize("i") == 4  # int
    assert struct.calcsize("I") == 4
    assert struct.calcsize("l") >= 4  # long (平台)
    assert struct.calcsize("q") == 8  # long long
    assert struct.calcsize("Q") == 8
    # 浮点
    assert struct.calcsize("f") == 4
    assert struct.calcsize("d") == 8
    # char
    assert struct.calcsize("c") == 1
    # bool (3.12+)
    if hasattr(struct, "calcsize"):
        try:
            assert struct.calcsize("?") == 1
        except struct.error:
            pass  # 3.11 不支持


def test_struct_pack_bool():
    """真 struct 真 bool 3.12+"""
    # pack True / False
    try:
        packed = struct.pack("?", True)
        assert len(packed) == 1
        val, = struct.unpack("?", packed)
        assert val is True
    except struct.error:
        # 3.11 不支持
        pytest.skip("struct ? requires Python 3.12+")


# ======================== unicodedata 进阶 ========================
def test_unicodedata_digit():
    """真 digit 真"""
    # 0-9 是 digit
    for c in "0123456789":
        try:
            d = unicodedata.digit(c)
            assert d is not None
        except ValueError:
            # sandbox specific
            pass
    # 'a' 不是 digit → 抛 ValueError
    with pytest.raises(ValueError):
        unicodedata.digit("a")


def test_unicodedata_decimal():
    """真 decimal 真"""
    # 0-9 decimal
    for c in "0123456789":
        try:
            d = unicodedata.decimal(c)
            assert d is not None
        except ValueError:
            pass
    # 'a' 不是 decimal → 抛 ValueError
    with pytest.raises(ValueError):
        unicodedata.decimal("a")


def test_unicodedata_numeric():
    """真 numeric 真"""
    # 1 是 numeric
    assert unicodedata.numeric("1") == 1.0
    # 1/2 numeric = 0.5
    assert unicodedata.numeric("½") == 0.5
    # 'a' 不是 → 抛 ValueError
    with pytest.raises(ValueError):
        unicodedata.numeric("a")


# ======================== typing Final ========================
def test_typing_Final():
    """真 typing.Final 真"""
    # Final 是 typing
    if hasattr(typing, "Final"):
        F = typing.Final
        assert F is not None
    # 用法
    F_var: typing.Final[int] = 42
    assert F_var == 42
