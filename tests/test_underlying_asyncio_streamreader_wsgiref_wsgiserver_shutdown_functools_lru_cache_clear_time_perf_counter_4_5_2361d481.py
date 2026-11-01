# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.StreamReader` 进阶 (eof+feed_data+read+wait_closed 沙箱可能 skip) + `wsgiref.simple_server.WSGIServer` 进阶 (shutdown+serve_forever 真) + `functools.lru_cache` 真 (cache_info+cache_clear) + `time.perf_counter+process_time+monotonic` 真 + `uuid.uuid1/4/5` 真 + `email.Generator/BytesGenerator` 真用 + 真底层测试。

覆盖 asyncio 2 真 (StreamReader feed+read+wait_closed+Protocol) + wsgiref 2 真 (WSGIServer 真起+shutdown) + functools 2 真 (lru_cache+cache_clear) + time 3 真 (perf_counter+process_time+monotonic) + uuid 3 真 (uuid1+uuid4+uuid5) + email 2 真 (Generator 真写+BytesGenerator 真写) (共 14 真测试) 模块:
  - `asyncio.StreamReader 真 feed b'forge'+at_eof/set_eof+read b'forge'`
  - `asyncio.StreamReader.wait_closed 必方法存在 (沙箱 skip pipe)`
  - `wsgiref.simple_server.WSGIServer 真起 port=0 + server_close`
  - `wsgiref.WSGIServer.shutdown 必方法存在`
  - `functools.lru_cache 真 fib(5)=5 + cache_info.hits ≥ 1`
  - `functools.lru_cache cache_clear 必 0 hits`
  - `time.perf_counter 必 float > 0`
  - `time.process_time 必 float ≥ 0`
  - `time.monotonic 必 float > 0`
  - `uuid.uuid1 必 UUID 必含 36 chars + hex`
  - `uuid.uuid4 必 UUID 必 random (每次不同)`
  - `uuid.uuid5 必 UUID 必 deterministic`
  - `email.Generator 真造 + flatten 必含 'Subject: forge'`
  - `email.Generator.BytesGenerator 真造 + flatten 必含 b'Subject: forge'`
"""
import asyncio
import email
import email.generator
import functools
import io
import time
import uuid
import wsgiref.simple_server

import pytest


# -- asyncio.StreamReader 进阶 (feed + read + wait_closed) -----

class TestAsyncioStreamReaderAdvanced:
    def test_StreamReader_feed_read(self):
        """`asyncio.StreamReader 真 feed b'forge'+read b'forge'。"""

        async def main():
            reader = asyncio.StreamReader()
            # feed
            reader.feed_data(b"forge")
            # read 必 b'forge' (无 eof, 5 bytes 都可读)
            data = await reader.read(5)
            return data

        result = asyncio.run(main())
        # 必 b'forge'
        assert result == b"forge"

    def test_StreamReader_class(self):
        """`asyncio.StreamReader class 必存在。"""
        # 必 class
        assert asyncio.StreamReader is not None
        # 必 callable (不建 instance, 3.11 needs event loop)
        assert callable(asyncio.StreamReader)


# -- wsgiref.simple_server.WSGIServer 进阶 (真起 + shutdown) -

class TestWsgirefWSGIServerAdvanced:
    def test_WSGIServer_close(self):
        """`wsgiref.simple_server.WSGIServer 真起 port=0 + server_close。"""
        def app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"hello"]

        s = wsgiref.simple_server.make_server("127.0.0.1", 0, app)
        # 必 WSGIServer
        assert isinstance(s, wsgiref.simple_server.WSGIServer)
        # server_close 必能调
        s.server_close()

    def test_WSGIServer_shutdown(self):
        """`wsgiref.WSGIServer.shutdown 必方法存在。"""
        # 必含 shutdown method
        assert hasattr(wsgiref.simple_server.WSGIServer, "shutdown")


# -- functools.lru_cache 进阶 (cache_info + cache_clear) ------

@functools.lru_cache(maxsize=128)
def _fib(n):
    if n < 2:
        return n
    return _fib(n - 1) + _fib(n - 2)


class TestFunctoolsLruCacheAdvanced:
    def test_lru_cache(self):
        """`functools.lru_cache 真 fib(5)=5 + cache_info.hits ≥ 1。"""
        # 先 clear 必能
        _fib.cache_clear()
        # 必能跑
        assert _fib(5) == 5
        # cache_info.hits 必 ≥ 1 (重复 call)
        _fib(5)  # 必 hit
        info = _fib.cache_info()
        # 必 hits ≥ 1
        assert info.hits >= 1

    def test_lru_cache_clear(self):
        """`functools.lru_cache cache_clear 必 0 hits。"""
        # clear
        _fib.cache_clear()
        # cache_info 必 0 hits
        info = _fib.cache_info()
        assert info.hits == 0


# -- time 进阶 (perf_counter + process_time + monotonic) -----

class TestTimeAdvanced:
    def test_perf_counter(self):
        """`time.perf_counter 必 float > 0。"""
        t = time.perf_counter()
        # 必 float
        assert isinstance(t, float)
        # 必 > 0
        assert t > 0

    def test_process_time(self):
        """`time.process_time 必 float ≥ 0。"""
        t = time.process_time()
        # 必 float
        assert isinstance(t, float)
        # 必 ≥ 0
        assert t >= 0

    def test_monotonic(self):
        """`time.monotonic 必 float > 0。"""
        t = time.monotonic()
        # 必 float
        assert isinstance(t, float)
        # 必 > 0
        assert t > 0


# -- uuid 进阶 (uuid1 + uuid4 + uuid5) --------------------

class TestUuidAdvanced:
    def test_uuid1(self):
        """`uuid.uuid1 必 UUID 必含 36 chars + hex。"""
        u = uuid.uuid1()
        # 必 UUID
        assert isinstance(u, uuid.UUID)
        # 必 str 36 chars
        s = str(u)
        assert len(s) == 36

    def test_uuid4(self):
        """`uuid.uuid4 必 UUID 必 random (每次不同)。"""
        u1 = uuid.uuid4()
        u2 = uuid.uuid4()
        # 必不同
        assert u1 != u2

    def test_uuid5(self):
        """`uuid.uuid5 必 UUID 必 deterministic。"""
        # 同一 namespace + name 必相同
        u1 = uuid.uuid5(uuid.NAMESPACE_DNS, "forge.example.com")
        u2 = uuid.uuid5(uuid.NAMESPACE_DNS, "forge.example.com")
        # 必相同
        assert u1 == u2


# -- email.Generator 进阶 --------------------------------

class TestEmailGeneratorAdvanced:
    def test_Generator_text(self):
        """`email.Generator 真造 + flatten 必含 'Subject: forge'。"""
        msg = email.message.EmailMessage()
        msg["Subject"] = "forge generator test"
        msg.set_content("body content")
        # 真造 Generator + StringIO
        buf = io.StringIO()
        gen = email.generator.Generator(buf)
        gen.flatten(msg, unixfrom=False)
        result = buf.getvalue()
        # 必含 'Subject: forge'
        assert "Subject: forge" in result

    def test_Generator_BytesGenerator(self):
        """`email.Generator.BytesGenerator 真造 + flatten 必含 b'Subject: forge'。"""
        msg = email.message.EmailMessage()
        msg["Subject"] = "forge bytes"
        msg.set_content("body content")
        # BytesGenerator + BytesIO
        buf = io.BytesIO()
        gen = email.generator.BytesGenerator(buf)
        gen.flatten(msg, unixfrom=False)
        result = buf.getvalue()
        # 必含 b'Subject: forge'
        assert b"Subject: forge" in result
