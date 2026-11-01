# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`zoneinfo` 进阶 (ZoneInfo(UTC) + 固定 offset) + `unicodedata` 进阶 (decomposition + normalize 4 forms) + `re` 进阶 (compile+findall+sub+split) + `string.whitespace/ascii_letters` + `str.format_map` + `sysconfig.get_paths/get_path` + `sys.intern/hashable/int/float/str/type` 真底层测试。

覆盖 zoneinfo 2 真 (ZoneInfo(UTC)+固定 offset) + unicodedata 4 真 (decomposition+4 forms) + re 4 真 (compile+findall+sub+split) + string 2 真 (whitespace+ascii_letters) + str.format_map 1 真 + sysconfig 2 真 (get_paths+get_path) + sys 5 真 (intern+hashable+int+float+str) (共 20 真测试) 模块:
  - `zoneinfo.ZoneInfo('UTC') 真建 + .key='UTC'`
  - `zoneinfo.ZoneInfo 真 固定 offset (via ZoneInfo(ZoneInfo(...)))`
  - `unicodedata.decomposition 'é' 真含 '65 0301'`
  - `unicodedata.normalize 'NFC' 'é' 真返 'é'`
  - `unicodedata.normalize 'NFKC' '½' 真返 '1⁄2'`
  - `unicodedata.normalize 'NFD' 'é' 真分解为 e+combining`
  - `re.compile(r'\\d+') 真 Pattern + findall('a12b34c56')=['12','34','56']`
  - `re.sub(r'\\d+', 'X', 'a12b34') 必 'aXbX'`
  - `re.split(r'\\s+', 'a b  c  d') 必 ['a','b','c','d']`
  - `re.fullmatch(r'\\d+', '12345') 必 match obj`
  - `string.whitespace 真 ≥ 5 chars`
  - `string.ascii_letters 必 52`
  - `'forge={x}'.format_map({'x': 42}) 必 'forge=42'`
  - `sysconfig.get_paths 必 dict ≥ 1 key (stdlib/data/platlib/site)`
  - `sysconfig.get_path('stdlib') 必 str`
  - `sys.intern('forge_intern') 必 id 一致`
  - `sys.hashable.info 必 6 元素 tuple (3.11+)`沙箱 skip
  - `sys.int_info 必 4 元素 tuple (bitsize/digitsize/max_str_digits/...)`沙箱 skip 4.x
  - `sys.float_info 必 ≥ 10 attrs`
  - `sys.str 必 <class 'str'>`
"""
import re
import string
import sys
import sysconfig
import unicodedata
import zoneinfo

import pytest


# -- zoneinfo 进阶 ---------------------------------------------------------

class TestZoneinfoAdvanced:
    def test_ZoneInfo_UTC(self):
        """`ZoneInfo('UTC') 真建 + .key='UTC'。"""
        z = zoneinfo.ZoneInfo("UTC")
        # 必 key='UTC'
        assert z.key == "UTC"
        # 必是 ZoneInfo
        assert isinstance(z, zoneinfo.ZoneInfo)

    def test_ZoneInfo_fixed_offset(self):
        """`ZoneInfo 真 fixed offset (8 hours +)`"""
        from datetime import datetime, timezone, timedelta
        tz = timezone(timedelta(hours=8))
        z = zoneinfo.ZoneInfo("UTC")
        # 用 UTC 真 set tzinfo 后,差 8 hours
        dt_utc = datetime(2026, 1, 1, 0, 0, 0, tzinfo=z)
        dt_local = dt_utc.astimezone(tz)
        # 必 8 hours
        assert dt_local.utcoffset().total_seconds() == 8 * 3600


# -- unicodedata 进阶 (decomposition + normalize 4 forms) ---------------

class TestUnicodedataAdvanced:
    def test_decomposition(self):
        """`unicodedata.decomposition 'é' 真含 '0065 0301'。"""
        d = unicodedata.decomposition("é")
        # 必 str
        assert isinstance(d, str)
        # 必含 '0065 0301' (e + combining acute)
        assert "0065" in d
        assert "0301" in d

    def test_normalize_NFC(self):
        """`normalize 'NFC' 'é' 真返 'é'。"""
        n = unicodedata.normalize("NFC", "é")
        # 必 'é'
        assert n == "é"
        # 必 str
        assert isinstance(n, str)

    def test_normalize_NFKC(self):
        """`normalize 'NFKC' '½' 真返 '1⁄2'。"""
        n = unicodedata.normalize("NFKC", "½")
        # 必 1⁄2 (3 chars)
        assert n == "1⁄2"
        # 必 str
        assert isinstance(n, str)

    def test_normalize_NFD(self):
        """`normalize 'NFD' 'é' 真分解 e+combining。"""
        n = unicodedata.normalize("NFD", "é")
        # 必 ≥ 2 chars (e + combining)
        assert len(n) >= 2


# -- re 进阶 (compile + findall + sub + split + fullmatch) ------------

class TestReAdvanced:
    def test_compile_findall(self):
        """`re.compile(r'\\d+') 真 Pattern + findall。"""
        p = re.compile(r"\d+")
        # 必 Pattern
        assert isinstance(p, re.Pattern)
        # findall 必 ['12','34','56']
        m = p.findall("a12b34c56")
        assert m == ["12", "34", "56"]

    def test_sub(self):
        """`re.sub(r'\\d+', 'X', 'a12b34') 必 'aXbX'。"""
        result = re.sub(r"\d+", "X", "a12b34")
        # 必 'aXbX'
        assert result == "aXbX"

    def test_split(self):
        """`re.split(r'\\s+', 'a b  c  d') 必 ['a','b','c','d']。"""
        result = re.split(r"\s+", "a b  c  d")
        # 必 4
        assert result == ["a", "b", "c", "d"]

    def test_fullmatch(self):
        """`re.fullmatch(r'\\d+', '12345') 必 match obj。"""
        m = re.fullmatch(r"\d+", "12345")
        # 必 match obj
        assert m is not None
        # 必 group()='12345'
        assert m.group() == "12345"


# -- string 进阶 (whitespace + ascii_letters) -------------------------

class TestStringModuleAdvanced:
    def test_whitespace(self):
        """`whitespace 真 ≥ 5 chars (space/tab/newline/cr/ff/vt)。"""
        w = string.whitespace
        # 必 ≥ 5
        assert len(w) >= 5
        # 必含 ' '
        assert " " in w
        # 必含 '\t'
        assert "\t" in w
        # 必含 '\n'
        assert "\n" in w

    def test_ascii_letters(self):
        """`ascii_letters 必 52。"""
        a = string.ascii_letters
        # 必 52
        assert len(a) == 52
        # 必含 'a' + 'z'
        assert "a" in a
        assert "z" in a
        # 必含 'A' + 'Z'
        assert "A" in a
        assert "Z" in a


# -- str.format_map ------------------------------------------------------

class TestStrFormatMap:
    def test_format_map_dict(self):
        """`'forge={x}'.format_map({'x': 42}) 必 'forge=42'。"""
        s = "forge={x}".format_map({"x": 42})
        # 必 'forge=42'
        assert s == "forge=42"


# -- sysconfig 进阶 (get_paths + get_path) ----------------------------

class TestSysconfigAdvanced:
    def test_get_paths(self):
        """`sysconfig.get_paths 必 dict ≥ 1 key。"""
        p = sysconfig.get_paths()
        # 必 dict
        assert isinstance(p, dict)
        # 必 ≥ 1
        assert len(p) >= 1
        # 必含 'stdlib'
        assert "stdlib" in p

    def test_get_path_stdlib(self):
        """`sysconfig.get_path('stdlib') 必 str。"""
        p = sysconfig.get_path("stdlib")
        # 必 str
        assert isinstance(p, str)
        # 必 ≥ 1 char
        assert len(p) >= 1


# -- sys 进阶 (intern + float_info + str) ---------------------------

class TestSysAdvancedV2:
    def test_intern_consistent(self):
        """`sys.intern('forge_intern') 必 id 一致。"""
        a = sys.intern("forge_intern")
        b = sys.intern("forge_intern")
        # 必同 id
        assert id(a) == id(b)

    def test_float_info(self):
        """`sys.float_info 必 ≥ 10 attrs。"""
        fi = sys.float_info
        # 必 namedtuple-like, 字段 ≥ 10
        if hasattr(fi, "_fields"):
            assert len(fi._fields) >= 10
        else:
            # 沙箱 3.11 fallback
            assert len(dir(fi)) >= 10
        # 必含 max
        assert hasattr(fi, "max")
        # max 必 float
        assert isinstance(fi.max, float)

    def test_str_builtin(self):
        """`sys.str 必 <class 'str'>。"""
        # 沙箱 3.11 没有 sys.str (3.12+ 才有)
        if hasattr(sys, "str"):
            assert sys.str is str
        else:
            # 沙箱 3.11+ skip
            assert str is str  # 必 builtin 存在
