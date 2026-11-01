# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`difflib` + `string` + `secrets` + `codecs` + `uuid` 进阶真底层测试。

覆盖文本比较 / 字符串模板 / 随机安全 / 编解码 / UUID 模块:
  - `difflib.SequenceMatcher.ratio` 真返 0~1 相似度
  - `difflib.unified_diff` 真生成 diff 含 ---/+++/-/+
  - `difflib.HtmlDiff.make_table` 真生成 HTML <table>
  - `difflib.get_close_matches` 真返最接近前 N
  - `string.Template('${name}').substitute(name='forge')` 真代入
  - `string.ascii_lowercase` 真含 26 个小写字母
  - `string.Formatter().format('{a[0]}', a=[1,2,3])` 真支持索引访问
  - `secrets.token_urlsafe(32)` 真返 URL-safe 字符串
  - `secrets.SystemRandom()` 真抽 random
  - `codecs.encode('hello', 'rot_13')` 真 ROT13 编解码
  - `codecs.encode('hello', 'base64')` 真 base64
  - `uuid.uuid4()` 真生成 4 个版本 UUID
  - `uuid.UUID('...')` 真解析
  - `uuid.uuid5(NAMESPACE_DNS, 'forge')` 真 deterministic UUID
  - `uuid.UUID.bytes` 真 16 字节
"""
import codecs
import difflib
import secrets
import string
import uuid

import pytest


# -- difflib ------------------------------------------------------------------

class TestDifflibAdvanced:
    def test_SequenceMatcher_ratio(self):
        """`SequenceMatcher.ratio` 真返 0~1 相似度。"""
        m = difflib.SequenceMatcher(None, "hello", "help")
        r = m.ratio()
        assert 0.0 < r < 1.0, f"ratio 应 ∈ (0,1),实际 {r}"
        # 完全相同 ratio=1
        m2 = difflib.SequenceMatcher(None, "forge", "forge")
        assert m2.ratio() == 1.0

    def test_unified_diff(self):
        """`difflib.unified_diff` 真生成 diff 含 ---/+++/-/+/。"""
        a = ["line1\n", "line2\n", "line3\n"]
        b = ["line1\n", "line2 modified\n", "line3\n"]
        diff = list(difflib.unified_diff(a, b, fromfile="a", tofile="b"))
        joined = "".join(diff)
        assert "--- a" in joined
        assert "+++ b" in joined
        assert "-line2" in joined
        assert "+line2 modified" in joined

    def test_HtmlDiff_make_table(self):
        """`difflib.HtmlDiff().make_table` 真返含 '<table' HTML。"""
        a = ["hello\n", "world\n"]
        b = ["hello\n", "forge\n"]
        html = difflib.HtmlDiff().make_table(a, b, fromdesc="A", todesc="B")
        assert "<table" in html.lower(), f"应含 <table,实际 {html[:200]!r}"
        assert "forge" in html

    def test_get_close_matches(self):
        """`get_close_matches` 真返前 N 接近项。"""
        words = ["apple", "ape", "apricot", "banana"]
        matches = difflib.get_close_matches("apl", words, n=2)
        assert len(matches) <= 2
        assert "ape" in matches  # 最接近


# -- string.Template ----------------------------------------------------------

class TestStringTemplate:
    def test_Template_substitute(self):
        """`Template('${name}').substitute(name='forge')` 真代入。"""
        t = string.Template("${name}-${version}")
        out = t.substitute(name="forgemind", version="2026.9")
        assert out == "forgemind-2026.9"

    def test_Template_safe_substitute_missing(self):
        """`safe_substitute` 缺字段保留 `${x}`,不抛。"""
        t = string.Template("${a} and ${b}")
        out = t.safe_substitute(a="forge")
        assert out == "forge and ${b}"

    def test_string_ascii_lowercase(self):
        """`string.ascii_lowercase` 真含 26 个小写字母。"""
        assert len(string.ascii_lowercase) == 26
        assert string.ascii_lowercase[0] == "a"
        assert string.ascii_lowercase[-1] == "z"

    def test_Formatter_index_access(self):
        """`Formatter().format('{a[0]}', a=[1,2,3])` 真支持索引访问。"""
        out = string.Formatter().format("a[0]={a[0]} a[1]={a[1]}", a=[10, 20, 30])
        assert out == "a[0]=10 a[1]=20"


# -- secrets ------------------------------------------------------------------

class TestSecretsAdvanced:
    def test_token_urlsafe(self):
        """`secrets.token_urlsafe(32)` 真返 URL-safe 字符串。"""
        t = secrets.token_urlsafe(32)
        # URL-safe base64 → 无 '+' '/' '='
        assert "+" not in t
        assert "/" not in t
        assert isinstance(t, str)
        # 不同调用返不同值
        assert secrets.token_urlsafe(32) != t

    def test_SystemRandom_random(self):
        """`secrets.SystemRandom()` 真抽 random。"""
        r = secrets.SystemRandom()
        # 5 个不同种子应返 5 个不同值(极高概率)
        values = [r.random() for _ in range(5)]
        assert all(0 <= v < 1 for v in values)
        # 至少 4 个不同(概率保证)
        assert len(set(values)) >= 4

    def test_SystemRandom_randbelow(self):
        """`secrets.randbelow(100)` 真返 [0, 100) 整数。"""
        for _ in range(50):
            n = secrets.randbelow(100)
            assert 0 <= n < 100


# -- codecs -------------------------------------------------------------------

class TestCodecs:
    def test_rot13_encode(self):
        """`codecs.encode('hello', 'rot_13')` 真 ROT13。"""
        out = codecs.encode("hello", "rot_13")
        assert out == "uryyb", f"hello ROT13 应=uryyb,实际 {out}"

    def test_rot13_round_trip(self):
        """ROT13 幂等,encode(decode(x)) == x。"""
        s = "forgemind"
        once = codecs.encode(s, "rot_13")
        twice = codecs.encode(once, "rot_13")
        assert twice == s

    def test_base64_encode_decode(self):
        """`codecs.encode(b'hello', 'base64')` 真 base64。"""
        enc = codecs.encode(b"hello", "base64").rstrip(b"\n")
        assert enc == b"aGVsbG8=", f"hello base64 应='aGVsbG8=',实际 {enc!r}"
        dec = codecs.decode(enc, "base64")
        assert dec == b"hello"

    def test_utf8_encode_decode(self):
        """`codecs.encode('中文', 'utf-8')` 真 UTF-8 字节。"""
        enc = codecs.encode("中文", "utf-8")
        assert enc == "中文".encode("utf-8")
        dec = codecs.decode(enc, "utf-8")
        assert dec == "中文"


# -- uuid ---------------------------------------------------------------------

class TestUuidAdvanced:
    def test_uuid4_generates_unique(self):
        """`uuid.uuid4()` 真生成 4 个版本 UUID,两次不同。"""
        a = uuid.uuid4()
        b = uuid.uuid4()
        assert a != b, "两次 uuid4 应不同"
        assert a.version == 4, f"version 应=4,实际 {a.version}"

    def test_uuid_parse_string(self):
        """`uuid.UUID('...')` 真解析,`version=4`。"""
        u = uuid.UUID("12345678-1234-4678-9234-567812345678")
        assert u.version == 4
        assert str(u) == "12345678-1234-4678-9234-567812345678"

    def test_uuid5_deterministic(self):
        """`uuid.uuid5(NAMESPACE_DNS, 'forge')` 真 deterministic。"""
        a = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")
        b = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")
        assert a == b, "uuid5 同 namespace+name 应返相同 UUID"
        assert a.version == 5

    def test_uuid_bytes_length(self):
        """`UUID.bytes` 真 16 字节。"""
        u = uuid.uuid4()
        assert len(u.bytes) == 16, f"UUID bytes 应=16 字节,实际 {len(u.bytes)}"
