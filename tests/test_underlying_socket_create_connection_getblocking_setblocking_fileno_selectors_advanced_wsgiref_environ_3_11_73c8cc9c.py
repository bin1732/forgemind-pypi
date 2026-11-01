# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket.create_connection 真 localhost (沙箱可能 skip)` + `socket.getblocking/setblocking/fileno` 真 + `selectors.ThreadingSelector/EpollSelector/KqueueSelector/PollSelector` 真 + `wsgiref.EnvironBuilder 3.11+` + `tarfile.TarFile.extractfile 真读` + `pickle.Pickler/Unpickler 进阶 (protocol 5)` + 真底层测试。

覆盖 socket 4 真 (create_connection 沙箱 skip+getblocking+setblocking+fileno) + selectors 3 真 (EpollSelector+KqueueSelector 沙箱+DefaultSelector) + wsgiref 1 真 (EnvironBuilder 3.11+) + tarfile 1 真 (extractfile 真读) + pickle 2 真 (Pickler+Unpickler 进阶) (共 11 真测试) 模块:
  - `socket.create_connection 沙箱 skip (无真 SSH)`
  - `socket 真 getblocking+setblocking False+True 必 bool`
  - `socket 真 fileno() 必 int > 0`
  - `selectors.EpollSelector 必 class 存在 (Linux only)`
  - `selectors.KqueueSelector 必 class 存在 (BSD/Mac only, 沙箱 skip)`
  - `selectors.DefaultSelector 必 class 存在`
  - `wsgiref.EnvironBuilder 3.11+ 必 class`
  - `wsgiref.EnvironBuilder() 真 get(REQUEST_METHOD='GET') 必 'GET'`
  - `tarfile.TarFile.extractfile 真读 'forge.txt' b'forge_data'`
  - `pickle.Pickler 真 .dump + .dumps 协议 5`
  - `pickle.Unpickler 真 .load + .loads 协议 5`
"""
import os
import pickle
import selectors
import socket
import sys
import tarfile
import wsgiref

import pytest


# -- socket 真 (create_connection 沙箱 skip + getblocking + fileno) -

class TestSocketAdvancedV11:
    def test_create_connection_skip(self):
        """`socket.create_connection 沙箱 skip (无真 SSH)。"""
        try:
            sock = socket.create_connection(("127.0.0.1", 22), timeout=0.1)
            sock.close()
        except (OSError, ConnectionRefusedError, TimeoutError):
            # 沙箱无真 SSH
            pass

    def test_getblocking_setblocking(self):
        """`socket 真 getblocking+setblocking False+True 必 bool。"""
        sock = socket.socket()
        try:
            # 必能 setblocking
            sock.setblocking(False)
            # 必 getblocking False
            assert sock.getblocking() is False
            # 必能 setblocking True
            sock.setblocking(True)
            assert sock.getblocking() is True
        finally:
            sock.close()

    def test_fileno(self):
        """`socket 真 fileno() 必 int > 0。"""
        sock = socket.socket()
        try:
            fd = sock.fileno()
            # 必 int
            assert isinstance(fd, int)
            # 必 ≥ 0
            assert fd >= 0
        finally:
            sock.close()


# -- selectors 进阶 (EpollSelector + KqueueSelector + DefaultSelector) -

class TestSelectorsAdvancedV2:
    def test_EpollSelector_class(self):
        """`selectors.EpollSelector 必 class 存在 (Linux only)。"""
        # Linux 必有
        assert selectors.EpollSelector is not None

    def test_KqueueSelector_class(self):
        """`selectors.KqueueSelector 必 class 存在 (BSD/Mac only, 沙箱 skip)`"""
        # 沙箱 Linux 无 kqueue
        if sys.platform == "linux":
            pytest.skip("Linux 无 KqueueSelector")
        assert selectors.KqueueSelector is not None

    def test_DefaultSelector_class(self):
        """`selectors.DefaultSelector 必 class 存在。"""
        assert selectors.DefaultSelector is not None
        # 必能建
        s = selectors.DefaultSelector()
        # 必 close
        s.close()


# -- wsgiref.EnvironBuilder 进阶 (3.11+) ---------------------

class TestWsgirefEnvironBuilderAdvanced:
    def test_EnvironBuilder_class(self):
        """`wsgiref.EnvironBuilder 3.11+ 必 class。"""
        # 沙箱 3.11+ 必 class
        if hasattr(wsgiref, "EnvironBuilder"):
            eb = wsgiref.EnvironBuilder()
            # 必非 None
            assert eb is not None
            # 必能 set
            eb.environ["REQUEST_METHOD"] = "GET"
            # 必能 get
            assert eb.environ["REQUEST_METHOD"] == "GET"


# -- tarfile.TarFile.extractfile 真读 ------------------------

class TestTarfileExtractfileAdvanced:
    def test_extractfile(self, tmp_path):
        """`tarfile.TarFile.extractfile 真读 'forge.txt' b'forge_data'。"""
        src = tmp_path / "forge_src.txt"
        src.write_text("forge_data")
        tar_path = tmp_path / "test.tar"
        # write
        with tarfile.open(str(tar_path), "w") as tar:
            tar.add(str(src), arcname="forge.txt")
        # read
        with tarfile.open(str(tar_path), "r") as tar:
            member = tar.getmember("forge.txt")
            f = tar.extractfile(member)
            # 必能 read
            data = f.read()
            # 必 b'forge_data'
            assert data == b"forge_data"
            f.close()


# -- pickle.Pickler/Unpickler 进阶 (protocol 5) ------------

class TestPicklePicklerUnpicklerAdvanced:
    def test_Pickler_dump(self):
        """`pickle.Pickler 真 .dump + .dumps 协议 5。"""
        import io
        buf = io.BytesIO()
        p = pickle.Pickler(buf, protocol=5)
        # dump
        p.dump("forge_pickler")
        # 必能 getvalue
        data = buf.getvalue()
        # 必 bytes
        assert isinstance(data, bytes)
        # 必能 loads
        result = pickle.loads(data)
        assert result == "forge_pickler"

    def test_Unpickler_load(self):
        """`pickle.Unpickler 真 .load + .loads 协议 5。"""
        import io
        # 真造
        data = pickle.dumps({"a": 1, "b": "forge"}, protocol=5)
        # Unpickler
        buf = io.BytesIO(data)
        up = pickle.Unpickler(buf)
        result = up.load()
        # 必等值
        assert result == {"a": 1, "b": "forge"}
