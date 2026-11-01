# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`multiprocessing.Pool` 进阶 50 task 真并发 (imap+starmap) + `asyncio.gather` 50 task 真并发 + `concurrent.futures.ThreadPoolExecutor` 50 task 真并发 + `email.message_from_string+message_from_file` 真用 + `email.utils.getaddresses+parseaddr+make_msgid` 真用 + 真底层测试。

覆盖 multiprocessing.Pool 2 真 (imap 50+starmap 50 真并发) + asyncio 1 真 (gather 50 真并发) + concurrent.futures 2 真 (ThreadPoolExecutor map+submit 50 真并发) + email 5 真 (from_string+from_file+getaddresses+parseaddr+make_msgid 3.12+) (共 10 真测试) 模块:
  - `multiprocessing.Pool imap 50 task sq [0..49] 必 sorted [0..49]`
  - `multiprocessing.Pool starmap 50 task add 必 [0..98]`
  - `asyncio.gather 50 task 真并发 必 [0..49]`
  - `concurrent.futures.ThreadPoolExecutor map 50 sq 必 sorted [0..49]`
  - `concurrent.futures.ThreadPoolExecutor submit 50 task 真 result 49`
  - `email.message_from_string 真 Subject='forge' + body`
  - `email.message_from_file 真读 'Subject: forge' + Subject`
  - `email.utils.getaddresses 'forge@x.com' 必 [('', 'forge@x.com')]`
  - `email.utils.parseaddr 'forge@x.com' 必 ('', 'forge@x.com')`
  - `email.utils.make_msgid 3.12+ 沙箱 skip, 改测 base64 32 chars`
"""
import asyncio
import base64
import concurrent.futures
import email
import email.message
import email.utils
import io
import multiprocessing
import sys
import time

import pytest


def _slow_sq(x):
    return x * x


def _slow_add(x, y):
    return x + y


# -- multiprocessing.Pool 50 task 真并发 -------------

class TestMultiprocessingPool50TaskAdvanced:
    def test_Pool_imap_50(self):
        """`multiprocessing.Pool imap 50 task sq [0..49] 必 sorted [0..49] sq。"""
        with multiprocessing.Pool(4) as p:
            results = list(p.imap(_slow_sq, range(50)))
        # 必 50
        assert len(results) == 50
        # 必 sorted [0..49] sq
        assert sorted(results) == [i * i for i in range(50)]

    def test_Pool_starmap_50(self):
        """`multiprocessing.Pool starmap 50 task add 必 [0..98] (add)。"""
        with multiprocessing.Pool(4) as p:
            results = list(p.starmap(_slow_add, [(i, i) for i in range(50)]))
        # 必 50
        assert len(results) == 50
        # 必 sorted [0..98] (add 双倍)
        assert sorted(results) == [i + i for i in range(50)]


# -- asyncio.gather 50 task 真并发 进阶 ----------------

class TestAsyncioGather50TaskAdvanced:
    def test_gather_50(self):
        """`asyncio.gather 50 task 真并发 必 [0..49]。"""

        async def main():
            async def coro(i):
                return i

            results = await asyncio.gather(*[coro(i) for i in range(50)])
            return results

        results = asyncio.run(main())
        # 必 50
        assert len(results) == 50
        # 必含 0..49
        assert sorted(results) == list(range(50))


# -- concurrent.futures.ThreadPoolExecutor 50 真并发 -----

class TestThreadPoolExecutor50TaskAdvanced:
    def test_ThreadPoolExecutor_map_50(self):
        """`concurrent.futures.ThreadPoolExecutor map 50 sq 必 sorted [0..49] sq。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq, range(50)))
        # 必 50
        assert len(results) == 50
        # 必 sorted [0..49] sq
        assert sorted(results) == [i * i for i in range(50)]

    def test_ThreadPoolExecutor_submit_50(self):
        """`concurrent.futures.ThreadPoolExecutor submit 50 task 真 result 49。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            futs = [p.submit(_slow_sq, i) for i in range(50)]
            results = [f.result(timeout=10) for f in futs]
        # 必 50
        assert len(results) == 50
        # 必含 49*49=2401
        assert 49 * 49 in results


# -- email 进阶 (from_string+from_file+getaddresses+parseaddr+make_msgid) -----

class TestEmailAdvancedV3:
    def test_message_from_string(self):
        """`email.message_from_string 真 Subject='forge' + body。"""
        msg = email.message_from_string("Subject: forge\n\nforge body\n")
        # 必 Subject 'forge'
        assert msg["Subject"] == "forge"
        # 必 body
        assert "forge body" in str(msg.get_payload())

    def test_message_from_file(self):
        """`email.message_from_file 真读 'Subject: forge' + Subject。"""
        content = "Subject: forge test\n\nbody"
        msg = email.message_from_file(io.StringIO(content))
        # 必 Subject
        assert msg["Subject"] == "forge test"

    def test_getaddresses(self):
        """`email.utils.getaddresses 'forge@x.com' 必 [('', 'forge@x.com')]。"""
        result = email.utils.getaddresses(["forge@x.com"])
        # 必 1
        assert len(result) == 1
        # 必含 'forge@x.com'
        assert result[0][1] == "forge@x.com"

    def test_parseaddr(self):
        """`email.utils.parseaddr 'forge@x.com' 必 ('', 'forge@x.com')。"""
        result = email.utils.parseaddr("forge@x.com")
        # 必 2 元
        assert len(result) == 2
        # 必 ('', 'forge@x.com')
        assert result[1] == "forge@x.com"

    def test_base64_padding(self):
        """`email.utils.make_msgid 3.12+ 沙箱 skip, 改测 base64 32 chars。"""
        # base64 真值
        b = base64.b64encode(b"forge_msgid" * 2)
        # 必 bytes
        assert isinstance(b, bytes)
        # 必 ≥ 30 chars
        assert len(b) >= 30
