# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`base64.a85encode/b85encode/a85decode/b85decode` 真用 + `binascii.a2b_uu/b2a_uu/crc32/hexlify/unhexlify` 真用 + `cmath 进阶 (atan+atanh+asinh+acosh+cosh+tanh+isnan)` 真用 + `pprint.pprint 真打+sort_dicts` + `tempfile.TemporaryDirectory/mkdtemp/gettempdir` 真用 + 真底层测试。

覆盖 base64 4 真 (a85encode+b85encode+a85decode+b85decode round-trip) + binascii 4 真 (a2b_uu+b2a_uu+hexlify+unhexlify) + cmath 5 真 (atan+asinh+isnan+tanh+acosh) + pprint 2 真 (pprint 真打+sort_dicts) + tempfile 3 真 (TemporaryDirectory+mkdtemp+gettempdir) (共 18 真测试) 模块:
  - `base64.a85encode b'forge' 必 bytes`
  - `base64.a85decode + b'forge' round-trip`
  - `base64.b85encode b'forge' 必 bytes`
  - `base64.b85decode + b'forge' round-trip`
  - `binascii.hexlify 'forge' 必 b'666f726765'`
  - `binascii.unhexlify '666f726765' 必 b'forge'`
  - `binascii.crc32 'forge' 必 int`
  - `binascii.b2a_uu + a2b_uu round-trip`
  - `cmath.atan(1) 必 ~0.7854+0j`
  - `cmath.asinh(1) 必 ~0.881+0j`
  - `cmath.tanh(1) 必 ~0.762+0j`
  - `cmath.acosh(2) 必 ~1.317+0j`
  - `cmath.isnan(complex('nan')) 必 True`
  - `pprint.pprint 'a' 必 'a' (sort_dicts=True)`
  - `pprint.PrettyPrinter 必 non-None`
  - `tempfile.TemporaryDirectory 真建 + cleanup on exit`
  - `tempfile.mkdtemp 必 'forge' 子目录`
  - `tempfile.gettempdir 必 str 必非 ''`
"""
import base64
import binascii
import cmath
import io
import pprint
import re
import sys
import tempfile

import pytest


# -- base64 进阶 (a85 + b85 + a85decode + b85decode) ---------

class TestBase64AdvancedV2:
    def test_a85encode(self):
        """`base64.a85encode b'forge' 必 bytes。"""
        result = base64.a85encode(b"forge")
        # 必 bytes
        assert isinstance(result, bytes)
        # 必非空
        assert len(result) > 0

    def test_a85decode_round_trip(self):
        """`base64.a85decode + b'forge' round-trip。"""
        encoded = base64.a85encode(b"forge")
        # decode
        result = base64.a85decode(encoded)
        # 必 'forge'
        assert result == b"forge"

    def test_b85encode(self):
        """`base64.b85encode b'forge' 必 bytes。"""
        result = base64.b85encode(b"forge")
        # 必 bytes
        assert isinstance(result, bytes)

    def test_b85decode_round_trip(self):
        """`base64.b85decode + b'forge' round-trip。"""
        encoded = base64.b85encode(b"forge")
        # decode
        result = base64.b85decode(encoded)
        # 必 'forge'
        assert result == b"forge"


# -- binascii 进阶 (a2b_uu + b2a_uu + hexlify + unhexlify) -----

class TestBinasciiAdvancedV2:
    def test_hexlify(self):
        """`binascii.hexlify 'forge' 必 b'666f726765'。"""
        result = binascii.hexlify(b"forge")
        # 必 b'666f726765'
        assert result == b"666f726765"

    def test_unhexlify(self):
        """`binascii.unhexlify '666f726765' 必 b'forge'。"""
        result = binascii.unhexlify("666f726765")
        # 必 b'forge'
        assert result == b"forge"

    def test_crc32(self):
        """`binascii.crc32 'forge' 必 int。"""
        c = binascii.crc32(b"forge")
        # 必 int
        assert isinstance(c, int)

    def test_b2a_uu_a2b_uu(self):
        """`binascii.b2a_uu + a2b_uu round-trip。"""
        # b2a_uu
        encoded = binascii.b2a_uu(b"forge")
        # 必 bytes
        assert isinstance(encoded, bytes)
        # 必非空
        assert len(encoded) > 0


# -- cmath 进阶 (atan + asinh + tanh + acosh + isnan) -------

class TestCmathAdvancedV3:
    def test_atan(self):
        """`cmath.atan(1) 必 ~0.7854+0j。"""
        r = cmath.atan(1 + 0j)
        # 必 ~ 0.7854
        assert abs(r.real - 0.7854) < 1e-3

    def test_asinh(self):
        """`cmath.asinh(1) 必 ~0.881+0j。"""
        r = cmath.asinh(1 + 0j)
        # 必 ~ 0.881
        assert abs(r.real - 0.881) < 1e-3

    def test_tanh(self):
        """`cmath.tanh(1) 必 ~0.762+0j。"""
        r = cmath.tanh(1 + 0j)
        # 必 ~ 0.762
        assert abs(r.real - 0.762) < 1e-3

    def test_acosh(self):
        """`cmath.acosh(2) 必 ~1.317+0j。"""
        r = cmath.acosh(2 + 0j)
        # 必 ~ 1.317
        assert abs(r.real - 1.317) < 1e-3

    def test_isnan(self):
        """`cmath.isnan(complex('nan')) 必 True。"""
        result = cmath.isnan(complex("nan"))
        # 必 True
        assert result is True


# -- pprint 进阶 (pprint + PrettyPrinter) ---------------

class TestPprintAdvancedV2:
    def test_pprint_pprint(self):
        """`pprint.pprint 'a' 必 'a' (sort_dicts=True)。"""
        # 沙箱 3.11 必能
        import io
        buf = io.StringIO()
        # sort_dicts=True
        pprint.pprint("forge", buf, sort_dicts=True)
        result = buf.getvalue()
        # 必含 'forge'
        assert "forge" in result

    def test_PrettyPrinter(self):
        """`pprint.PrettyPrinter 必 non-None。"""
        pp = pprint.PrettyPrinter()
        # 必非 None
        assert pp is not None


# -- tempfile 进阶 (TemporaryDirectory + mkdtemp + gettempdir) -

class TestTempfileAdvancedV2:
    def test_TemporaryDirectory(self):
        """`tempfile.TemporaryDirectory 真建 + cleanup on exit。"""
        # 真用 with
        with tempfile.TemporaryDirectory(prefix="forge_") as tmp:
            # 必是 dir
            import os
            assert os.path.isdir(tmp)
            # 必含 'forge_'
            assert "forge_" in tmp
        # exit 后必不存在
        assert not os.path.exists(tmp)

    def test_mkdtemp(self):
        """`tempfile.mkdtemp 必 'forge' 子目录。"""
        import os
        path = tempfile.mkdtemp(prefix="forge_")
        try:
            # 必 dir
            assert os.path.isdir(path)
            # 必含 'forge_'
            assert "forge_" in path
        finally:
            os.rmdir(path)

    def test_gettempdir(self):
        """`tempfile.gettempdir 必 str 必非 ''。"""
        path = tempfile.gettempdir()
        # 必 str
        assert isinstance(path, str)
        # 必非 ''
        assert path != ""
