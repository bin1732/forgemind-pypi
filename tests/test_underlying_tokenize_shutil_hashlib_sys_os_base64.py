# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 tokenize 真 (NL/COMMENT 真) + 真 shutil 真 (disk_usage 真 + get_terminal_size 真) + 真 hashlib 真 (sha3 真) + 真 sys 真 (getrecursionlimit/setrecursionlimit) + 真 os 真 (sep / linesep) + 真 base64 真.
全 stdlib, 零模拟。
"""
import tokenize
import shutil
import hashlib
import sys
import os
import base64
import io
import pytest


# ======================== tokenize 进阶 ========================
def test_tokenize_NL_COMMENT():
    """真 tokenize NL / COMMENT 进阶"""
    src = "# comment\nx = 1\n"
    tokens = list(tokenize.tokenize(io.BytesIO(src.encode()).readline))
    # 必有 COMMENT (#), NL (newline), NAME (x), OP (=), NUMBER (1), NEWLINE
    token_strs = [(t.string, t.type) for t in tokens]
    assert any(t[1] == tokenize.COMMENT and "# comment" in t[0] for t in token_strs)


def test_tokenize_indent_dedent():
    """真 tokenize INDENT/DEDENT 进阶"""
    src = "def f():\n    x = 1\n    y = 2\n"
    tokens = list(tokenize.tokenize(io.BytesIO(src.encode()).readline))
    # 必有 INDENT, DEDENT
    assert any(t.type == tokenize.INDENT for t in tokens)
    assert any(t.type == tokenize.DEDENT for t in tokens)


# ======================== shutil 进阶 ========================
def test_shutil_disk_usage():
    """真 disk_usage 真"""
    usage = shutil.disk_usage("/")
    # named tuple
    assert hasattr(usage, "total")
    assert hasattr(usage, "used")
    assert hasattr(usage, "free")
    # ≥ 0
    assert usage.total >= 0
    assert usage.used >= 0
    assert usage.free >= 0


def test_shutil_get_terminal_size():
    """真 get_terminal_size 进阶"""
    size = shutil.get_terminal_size()
    assert hasattr(size, "columns")
    assert hasattr(size, "lines")
    # ≥ 0
    assert size.columns >= 0
    assert size.lines >= 0


# ======================== hashlib 进阶 ========================
def test_hashlib_sha3_256():
    """真 SHA3-256 真"""
    h = hashlib.sha3_256()
    h.update(b"abc")
    digest = h.hexdigest()
    # SHA3-256("abc") = 3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532
    assert digest == "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532"


def test_hashlib_sha3_512():
    """真 SHA3-512 真"""
    h = hashlib.sha3_512()
    h.update(b"abc")
    digest = h.hexdigest()
    # SHA3-512("abc") = b751850b1a57168a5693cd924b6b096e08f621827444f70d884f5d0240d2712e10e116e9192af3c91a7ec57647e3934057340b4cf408d5a56592f8274eec53f0
    assert digest == "b751850b1a57168a5693cd924b6b096e08f621827444f70d884f5d0240d2712e10e116e9192af3c91a7ec57647e3934057340b4cf408d5a56592f8274eec53f0"


def test_hashlib_blake2s():
    """真 blake2s 真"""
    h = hashlib.blake2s()
    h.update(b"abc")
    digest = h.hexdigest()
    # blake2s("abc") = 508c5e8c327c14e2e1a72ba34eeb452f37458b209ed63a294d999b4c86675982
    assert digest == "508c5e8c327c14e2e1a72ba34eeb452f37458b209ed63a294d999b4c86675982"


# ======================== sys 进阶 ========================
def test_sys_getrecursionlimit():
    """真 getrecursionlimit 真"""
    limit = sys.getrecursionlimit()
    assert limit > 0
    # 通常 1000
    assert limit >= 100


def test_sys_setrecursionlimit():
    """真 setrecursionlimit 真往返"""
    old = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(2000)
        assert sys.getrecursionlimit() == 2000
    finally:
        # 恢复
        sys.setrecursionlimit(old)
    # 恢复
    assert sys.getrecursionlimit() == old


def test_sys_getsizeof():
    """真 getsizeof 真"""
    size = sys.getsizeof("")
    # 必 ≥ 0
    assert size > 0
    # bytes 必 ≥ 0
    assert sys.getsizeof(b"") > 0


# ======================== os 真 ========================
def test_os_sep():
    """真 os.sep 真"""
    # Linux/Darwin: /, Windows: \\
    assert os.sep in ("/", "\\")


def test_os_linesep():
    """真 os.linesep 真"""
    # Linux: \n, Windows: \r\n, Mac: \r
    assert os.linesep in ("\n", "\r\n", "\r")


# ======================== base64 进阶 ========================
def test_base64_b64encode_decode():
    """真 base64 b64encode/b64decode 真 round-trip"""
    data = b"hello"
    encoded = base64.b64encode(data)
    # aGVsbG8=
    assert encoded == b"aGVsbG8="
    decoded = base64.b64decode(encoded)
    assert decoded == data


def test_base64_urlsafe():
    """真 base64 urlsafe 真 round-trip"""
    data = b">?"
    encoded = base64.urlsafe_b64encode(data)
    decoded = base64.urlsafe_b64decode(encoded)
    assert decoded == data


def test_base64_b32encode():
    """真 b32encode 真"""
    data = b"abc"
    encoded = base64.b32encode(data)
    # round-trip
    decoded = base64.b32decode(encoded)
    assert decoded == data
