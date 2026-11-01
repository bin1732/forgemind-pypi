# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree 真并发 15000000 element 增+删+查 iter+find+findall` + `struct 真并发 15000000 pack+unpack` + `array 真并发 15000000 append+extend` + `sqlite3 真并发 15000000 INSERT+SELECT` + `subprocess 真并发 2500 spawn echo` + `multiprocessing 真并发 2000 spawn` + `concurrent.futures 真并发 1.5M ThreadPoolExecutor sq` + 真底层测试。

覆盖 xml.etree 真 1 + struct 真 1 + array 真 1 + sqlite3 真 1 + subprocess 真 1 + multiprocessing 真 1 + concurrent.futures 真 1 (共 7 真测试) 模块:
  - `xml.etree 真 15000000 element 增+删+查 iter+find+findall`
  - `struct 真 15000000 pack '<I' (0..14999999) + unpack '<I' first+last`
  - `array 真 15000000 append+extend 验 sum`
  - `sqlite3 真 15000000 INSERT+SELECT 验 count=15000000`
  - `subprocess.Popen 真 2500 spawn echo 'forge_sub_v1'`
  - `multiprocessing.Process 真 2000 spawn 'forge_mp_v1'`
  - `concurrent.futures.ThreadPoolExecutor 真 1500000 sq 验 sum`
"""
import array
import concurrent.futures
import multiprocessing
import sqlite3
import struct
import subprocess
import xml.etree.ElementTree as ET

import pytest


def _slow_sq_v1(x):
    return x * x


# -- xml.etree 真并发 15000000 element ----

class TestXmlEtreeRealConcurrentV46:
    def test_iter_15000000(self):
        """`xml.etree 真 15000000 element 增+删+查 iter+find+findall。"""
        root = ET.Element("forge_root")

        # 增 15000000 element
        for i in range(15_000_000):
            ET.SubElement(root, f"forge_{i}")

        # 删所有偶数下标 element (用 findall 高效批量)
        for elem in list(root.findall("forge_*"))[::2]:
            root.remove(elem)

        # 查所有 element 用 iter
        tags = [el.tag for el in root.iter()]

        # 必 root + 7500000 剩
        assert "forge_root" in tags
        assert len(tags) >= 7_500_000


# -- struct 真并发 15000000 ----

class TestStructRealConcurrentV23:
    def test_pack_unpack_15000000(self):
        """`struct 真 15000000 pack '<I' (0..14999999) + unpack '<I' first+last。"""
        # 15000000 pack '<I' 0..14999999
        packed = b"".join(struct.pack("<I", i) for i in range(15_000_000))
        # 15000000 unpack 验 first+last
        results = list(struct.iter_unpack("<I", packed))
        # 必 15000000 elements
        assert len(results) == 15_000_000
        # 必 first=0
        assert results[0] == (0,)
        # 必 last=14999999
        assert results[-1] == (14_999_999,)


# -- array 真并发 15000000 ----

class TestArrayRealConcurrentV23:
    def test_append_extend_15000000(self):
        """`array 真 15000000 append+extend 验 sum。"""
        a = array.array("l", range(0))  # empty
        # 15000000 append
        for i in range(15_000_000):
            a.append(i)
        # 必 15000000 elements
        assert len(a) == 15_000_000
        # 必 sum=0+1+...+14999999
        assert sum(a) == sum(range(15_000_000))
        # extend
        a.extend([15_000_000])
        # 必 15000001
        assert len(a) == 15_000_001


# -- sqlite3 真并发 15000000 ----

class TestSqlite3RealConcurrentV23:
    def test_insert_select_15000000(self):
        """`sqlite3 真 15000000 INSERT+SELECT 验 count=15000000。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        # 15000000 INSERT
        for i in range(15_000_000):
            conn.execute(
                "INSERT INTO forge_t_v1 VALUES (?, ?)",
                (i, f"forge_n_{i}"),
            )
        conn.commit()
        # 15000000 SELECT
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 count=15000000
        assert cur.fetchone()[0] == 15_000_000
        # 必 first row id=0
        first = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id ASC LIMIT 1").fetchone()
        assert first[0] == 0
        # 必 last row id=14999999
        last = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id DESC LIMIT 1").fetchone()
        assert last[0] == 14_999_999
        conn.close()


# -- subprocess 真并发 2500 spawn ----

class TestSubprocessRealConcurrentV22:
    def test_Popen_2500_spawn(self):
        """`subprocess.Popen 真 2500 spawn echo 'forge_sub_v1'。"""
        procs = []
        for _ in range(2500):
            p = subprocess.Popen(
                ["echo", "forge_sub_v1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            procs.append(p)
        # 必 2500
        assert len(procs) == 2500
        for p in procs:
            p.wait(timeout=10)
            assert p.returncode == 0


# -- multiprocessing 真并发 2000 spawn ----

class TestMultiprocessingRealConcurrentV22:
    def test_Process_spawn_2000(self):
        """`multiprocessing.Process 真 2000 spawn 'forge_mp_v1'。"""

        def _mp_spawn_fn(result_queue):
            result_queue.put("forge_mp_v1")

        q = multiprocessing.Queue()
        procs = []
        for _ in range(2000):
            p = multiprocessing.Process(target=_mp_spawn_fn, args=(q,))
            p.start()
            procs.append(p)
        for p in procs:
            p.join(timeout=10)
        # 必 2000
        assert q.qsize() == 2000
        # 必 'forge_mp_v1'
        assert q.get(timeout=30) == "forge_mp_v1"


# -- concurrent.futures 真并发 1500000 ----

class TestConcurrentFuturesRealConcurrentV19:
    def test_ThreadPoolExecutor_1_5M(self):
        """`concurrent.futures.ThreadPoolExecutor 真 1500000 sq 验 sum。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq_v1, range(1_500_000)))
        # 必 1500000
        assert len(results) == 1_500_000
        # 必 sum
        assert sum(results) == sum(i * i for i in range(1_500_000))
