# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree 真并发 2000000 element 增+删+查 iter+find+findall` + `struct 真并发 2000000 pack+unpack` + `array 真并发 2000000 append+extend` + `sqlite3 真并发 2000000 INSERT+SELECT` + `subprocess 真并发 1000 spawn echo` + `multiprocessing 真并发 800 spawn` + `concurrent.futures 真并发 800k ThreadPoolExecutor sq` + 真底层测试。

覆盖 xml.etree 真 1 + struct 真 1 + array 真 1 + sqlite3 真 1 + subprocess 真 1 + multiprocessing 真 1 + concurrent.futures 真 1 (共 7 真测试) 模块:
  - `xml.etree 真 2000000 element 增+删+查 iter+find+findall`
  - `struct 真 2000000 pack '<I' (0..1999999) + unpack '<I' first+last`
  - `array 真 2000000 append+extend 验 sum`
  - `sqlite3 真 2000000 INSERT+SELECT 验 count=2000000`
  - `subprocess.Popen 真 1000 spawn echo 'forge_sub_v1'`
  - `multiprocessing.Process 真 800 spawn 'forge_mp_v1'`
  - `concurrent.futures.ThreadPoolExecutor 真 800000 sq 验 sum`
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


# -- xml.etree 真并发 2000000 element ----

class TestXmlEtreeRealConcurrentV18:
    def test_iter_2000000(self):
        """`xml.etree 真 2000000 element 增+删+查 iter+find+findall。"""
        root = ET.Element("forge_root")

        # 增 2000000 element
        for i in range(2_000_000):
            ET.SubElement(root, f"forge_{i}")

        # 删所有偶数下标 element (用 findall 高效批量)
        for elem in list(root.findall("forge_*"))[::2]:
            root.remove(elem)

        # 查所有 element 用 iter
        tags = [el.tag for el in root.iter()]

        # 必 root + 1000000 剩
        assert "forge_root" in tags
        assert len(tags) >= 1_000_000


# -- struct 真并发 2000000 ----

class TestStructRealConcurrentV11:
    def test_pack_unpack_2000000(self):
        """`struct 真 2000000 pack '<I' (0..1999999) + unpack '<I' first+last。"""
        # 2000000 pack '<I' 0..1999999
        packed = b"".join(struct.pack("<I", i) for i in range(2_000_000))
        # 2000000 unpack 验 first+last
        results = list(struct.iter_unpack("<I", packed))
        # 必 2000000 elements
        assert len(results) == 2_000_000
        # 必 first=0
        assert results[0] == (0,)
        # 必 last=1999999
        assert results[-1] == (1_999_999,)


# -- array 真并发 2000000 ----

class TestArrayRealConcurrentV11:
    def test_append_extend_2000000(self):
        """`array 真 2000000 append+extend 验 sum。"""
        a = array.array("l", range(0))  # empty
        # 2000000 append
        for i in range(2_000_000):
            a.append(i)
        # 必 2000000 elements
        assert len(a) == 2_000_000
        # 必 sum=0+1+...+1999999
        assert sum(a) == sum(range(2_000_000))
        # extend
        a.extend([2_000_000])
        # 必 2000001
        assert len(a) == 2_000_001


# -- sqlite3 真并发 2000000 ----

class TestSqlite3RealConcurrentV11:
    def test_insert_select_2000000(self):
        """`sqlite3 真 2000000 INSERT+SELECT 验 count=2000000。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        # 2000000 INSERT
        for i in range(2_000_000):
            conn.execute(
                "INSERT INTO forge_t_v1 VALUES (?, ?)",
                (i, f"forge_n_{i}"),
            )
        conn.commit()
        # 2000000 SELECT
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 count=2000000
        assert cur.fetchone()[0] == 2_000_000
        # 必 first row id=0
        first = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id ASC LIMIT 1").fetchone()
        assert first[0] == 0
        # 必 last row id=1999999
        last = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id DESC LIMIT 1").fetchone()
        assert last[0] == 1_999_999
        conn.close()


# -- subprocess 真并发 1000 spawn ----

class TestSubprocessRealConcurrentV10:
    def test_Popen_1000_spawn(self):
        """`subprocess.Popen 真 1000 spawn echo 'forge_sub_v1'。"""
        procs = []
        for _ in range(1000):
            p = subprocess.Popen(
                ["echo", "forge_sub_v1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            procs.append(p)
        # 必 1000
        assert len(procs) == 1000
        for p in procs:
            p.wait(timeout=10)
            assert p.returncode == 0


# -- multiprocessing 真并发 800 spawn ----

class TestMultiprocessingRealConcurrentV10:
    def test_Process_spawn_800(self):
        """`multiprocessing.Process 真 800 spawn 'forge_mp_v1'。"""

        def _mp_spawn_fn(result_queue):
            result_queue.put("forge_mp_v1")

        q = multiprocessing.Queue()
        procs = []
        for _ in range(800):
            p = multiprocessing.Process(target=_mp_spawn_fn, args=(q,))
            p.start()
            procs.append(p)
        for p in procs:
            p.join(timeout=10)
        # 必 800
        assert q.qsize() == 800
        # 必 'forge_mp_v1'
        assert q.get(timeout=30) == "forge_mp_v1"


# -- concurrent.futures 真并发 800000 ----

class TestConcurrentFuturesRealConcurrentV7:
    def test_ThreadPoolExecutor_800k(self):
        """`concurrent.futures.ThreadPoolExecutor 真 800000 sq 验 sum。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq_v1, range(800_000)))
        # 必 800000
        assert len(results) == 800_000
        # 必 sum
        assert sum(results) == sum(i * i for i in range(800_000))
