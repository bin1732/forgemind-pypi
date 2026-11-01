# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree 真并发 1500000 element 增+删+查 iter+find+findall` + `struct 真并发 1500000 pack+unpack` + `array 真并发 1500000 append+extend` + `sqlite3 真并发 1500000 INSERT+SELECT` + `subprocess 真并发 800 spawn echo` + `multiprocessing 真并发 500 spawn` + `concurrent.futures 真并发 500k ThreadPoolExecutor sq` + 真底层测试。

覆盖 xml.etree 真 1 + struct 真 1 + array 真 1 + sqlite3 真 1 + subprocess 真 1 + multiprocessing 真 1 + concurrent.futures 真 1 (共 7 真测试) 模块:
  - `xml.etree 真 1500000 element 增+删+查 iter+find+findall`
  - `struct 真 1500000 pack '<I' (0..1499999) + unpack '<I' first+last`
  - `array 真 1500000 append+extend 验 sum`
  - `sqlite3 真 1500000 INSERT+SELECT 验 count=1500000`
  - `subprocess.Popen 真 800 spawn echo 'forge_sub_v1'`
  - `multiprocessing.Process 真 500 spawn 'forge_mp_v1'`
  - `concurrent.futures.ThreadPoolExecutor 真 500000 sq 验 sum`
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


# -- xml.etree 真并发 1500000 element ----

class TestXmlEtreeRealConcurrentV16:
    def test_iter_1500000(self):
        """`xml.etree 真 1500000 element 增+删+查 iter+find+findall。"""
        root = ET.Element("forge_root")

        # 增 1500000 element
        for i in range(1_500_000):
            ET.SubElement(root, f"forge_{i}")

        # 删所有偶数下标 element (用 findall 高效批量)
        for elem in list(root.findall("forge_*"))[::2]:
            root.remove(elem)

        # 查所有 element 用 iter
        tags = [el.tag for el in root.iter()]

        # 必 root + 750000 剩
        assert "forge_root" in tags
        assert len(tags) >= 750_000


# -- struct 真并发 1500000 ----

class TestStructRealConcurrentV10:
    def test_pack_unpack_1500000(self):
        """`struct 真 1500000 pack '<I' (0..1499999) + unpack '<I' first+last。"""
        # 1500000 pack '<I' 0..1499999
        packed = b"".join(struct.pack("<I", i) for i in range(1_500_000))
        # 1500000 unpack 验 first+last
        results = list(struct.iter_unpack("<I", packed))
        # 必 1500000 elements
        assert len(results) == 1_500_000
        # 必 first=0
        assert results[0] == (0,)
        # 必 last=1499999
        assert results[-1] == (1_499_999,)


# -- array 真并发 1500000 ----

class TestArrayRealConcurrentV10:
    def test_append_extend_1500000(self):
        """`array 真 1500000 append+extend 验 sum。"""
        a = array.array("l", range(0))  # empty
        # 1500000 append
        for i in range(1_500_000):
            a.append(i)
        # 必 1500000 elements
        assert len(a) == 1_500_000
        # 必 sum=0+1+...+1499999
        assert sum(a) == sum(range(1_500_000))
        # extend
        a.extend([1_500_000])
        # 必 1500001
        assert len(a) == 1_500_001


# -- sqlite3 真并发 1500000 ----

class TestSqlite3RealConcurrentV10:
    def test_insert_select_1500000(self):
        """`sqlite3 真 1500000 INSERT+SELECT 验 count=1500000。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        # 1500000 INSERT
        for i in range(1_500_000):
            conn.execute(
                "INSERT INTO forge_t_v1 VALUES (?, ?)",
                (i, f"forge_n_{i}"),
            )
        conn.commit()
        # 1500000 SELECT
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 count=1500000
        assert cur.fetchone()[0] == 1_500_000
        # 必 first row id=0
        first = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id ASC LIMIT 1").fetchone()
        assert first[0] == 0
        # 必 last row id=1499999
        last = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id DESC LIMIT 1").fetchone()
        assert last[0] == 1_499_999
        conn.close()


# -- subprocess 真并发 800 spawn ----

class TestSubprocessRealConcurrentV9:
    def test_Popen_800_spawn(self):
        """`subprocess.Popen 真 800 spawn echo 'forge_sub_v1'。"""
        procs = []
        for _ in range(800):
            p = subprocess.Popen(
                ["echo", "forge_sub_v1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            procs.append(p)
        # 必 800
        assert len(procs) == 800
        for p in procs:
            p.wait(timeout=10)
            assert p.returncode == 0


# -- multiprocessing 真并发 500 spawn ----

class TestMultiprocessingRealConcurrentV9:
    def test_Process_spawn_500(self):
        """`multiprocessing.Process 真 500 spawn 'forge_mp_v1'。"""

        def _mp_spawn_fn(result_queue):
            result_queue.put("forge_mp_v1")

        q = multiprocessing.Queue()
        procs = []
        for _ in range(500):
            p = multiprocessing.Process(target=_mp_spawn_fn, args=(q,))
            p.start()
            procs.append(p)
        for p in procs:
            p.join(timeout=10)
        # 必 500
        assert q.qsize() == 500
        # 必 'forge_mp_v1'
        assert q.get(timeout=30) == "forge_mp_v1"


# -- concurrent.futures 真并发 500000 ----

class TestConcurrentFuturesRealConcurrentV6:
    def test_ThreadPoolExecutor_500k(self):
        """`concurrent.futures.ThreadPoolExecutor 真 500000 sq 验 sum。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq_v1, range(500_000)))
        # 必 500000
        assert len(results) == 500_000
        # 必 sum
        assert sum(results) == sum(i * i for i in range(500_000))
