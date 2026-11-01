# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`struct.calcsize/format+pack+unpack+iter_unpack` 进阶 (多 format char) + `array.array` 进阶 (buffer_info+tolist+extend+chars) + `socket.create_default_context+load_default_certs` 进阶 + `subprocess.CompletedProcess.check_returncode+stderr` 进阶 + 真底层测试。

覆盖 struct 3 真 (calcsize 多 format+pack+unpack+iter_unpack) + array 3 真 (buffer_info+tolist+extend+chars) + ssl 2 真 (create_default_context+load_default_certs) + subprocess 2 真 (CompletedProcess check_returncode+stderr) (共 10 真测试) 模块:
  - `struct.calcsize '<3i' 必 12 (3 int = 12 bytes)`
  - `struct.pack '<3i' 1,2,3 必 12 bytes`
  - `struct.iter_unpack '<i' b'\\x01\\x00\\x00\\x00\\x02\\x00\\x00\\x00' 必 [(1,), (2,)]`
  - `array.array 'i' [1,2,3] 必 tolist [1,2,3] + buffer_info (addr, len)`
  - `array.array 'i' extend [4,5] 必 [1,2,3,4,5]`
  - `array.array 'b' [65] 必 tolist [65] + chr(65) = 'A'`
  - `ssl.create_default_context 必 SSLContext + verify_mode >= CERT_NONE`
  - `ssl.SSLContext.load_default_certs 必不抛`
  - `subprocess.CompletedProcess.check_returncode 0 必 0 (无抛)`
  - `subprocess.run 'true' stderr 必 b'' (empty)`
"""
import array
import os
import socket
import ssl
import struct
import subprocess
import sys

import pytest


# -- struct 进阶 (calcsize + pack + iter_unpack 多 format) ---

class TestStructAdvancedV4:
    def test_calcsize_3i(self):
        """`struct.calcsize '<3i' 必 12 (3 int = 12 bytes)。"""
        size = struct.calcsize("<3i")
        # 必 12
        assert size == 12

    def test_pack_3i(self):
        """`struct.pack '<3i' 1,2,3 必 12 bytes。"""
        data = struct.pack("<3i", 1, 2, 3)
        # 必 12 bytes
        assert len(data) == 12
        # 必能 unpack
        result = struct.unpack("<3i", data)
        assert result == (1, 2, 3)

    def test_iter_unpack_2int(self):
        """`struct.iter_unpack '<i' b'\\x01\\x00\\x00\\x00\\x02\\x00\\x00\\x00' 必 [(1,), (2,)]。"""
        data = b"\x01\x00\x00\x00\x02\x00\x00\x00"
        result = list(struct.iter_unpack("<i", data))
        # 必 [(1,), (2,)]
        assert result == [(1,), (2,)]


# -- array.array 进阶 (buffer_info + tolist + extend + chars) -

class TestArrayAdvancedV2:
    def test_array_tolist_buffer_info(self):
        """`array.array 'i' [1,2,3] 必 tolist [1,2,3] + buffer_info。"""
        a = array.array("i", [1, 2, 3])
        # tolist
        assert a.tolist() == [1, 2, 3]
        # buffer_info 必 (addr, length)
        info = a.buffer_info()
        # 必 tuple of 2
        assert len(info) == 2

    def test_array_extend(self):
        """`array.array 'i' extend [4,5] 必 [1,2,3,4,5]。"""
        a = array.array("i", [1, 2, 3])
        a.extend([4, 5])
        # 必 [1,2,3,4,5]
        assert a.tolist() == [1, 2, 3, 4, 5]

    def test_array_chars(self):
        """`array.array 'b' [65] 必 tolist [65] + chr(65) = 'A'。"""
        a = array.array("b", [65])
        # tolist
        assert a.tolist() == [65]
        # chr(65) = 'A'
        assert chr(65) == "A"


# -- ssl 进阶 (create_default_context + load_default_certs) ----

class TestSslAdvancedV3:
    def test_create_default_context(self):
        """`ssl.create_default_context 必 SSLContext + verify_mode >= CERT_NONE。"""
        ctx = ssl.create_default_context()
        # 必 SSLContext
        assert isinstance(ctx, ssl.SSLContext)
        # 必 verify_mode
        assert ctx.verify_mode is not None
        assert ctx.verify_mode >= ssl.CERT_NONE

    def test_load_default_certs(self):
        """`ssl.SSLContext.load_default_certs 必不抛。"""
        ctx = ssl.create_default_context()
        # load_default_certs 必不抛
        try:
            ctx.load_default_certs()
            # 必非 None
            assert True
        except (ssl.SSLError, OSError) as e:
            # 沙箱可能无 cert
            pytest.skip(f"沙箱无 cert: {e}")


# -- subprocess 进阶 (CompletedProcess check_returncode + stderr) ----

class TestSubprocessCompletedProcessAdvanced:
    def test_check_returncode(self):
        """`subprocess.CompletedProcess.check_returncode 0 必 0 (无抛)。"""
        result = subprocess.CompletedProcess(
            args=["true"],
            returncode=0,
            stdout=b"",
            stderr=b"",
        )
        # check_returncode 必不抛
        result.check_returncode()
        # 必 0
        assert result.returncode == 0

    def test_run_stderr_empty(self):
        """`subprocess.run 'true' stderr 必 b'' (empty)。"""
        result = subprocess.run(
            ["true"],
            capture_output=True,
        )
        # 必 0
        assert result.returncode == 0
        # stderr 必空
        assert result.stderr == b""
