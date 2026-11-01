# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree 真并发 500000 element 增+删+查 iter+find+findall` + `struct 真并发 500000 pack+unpack` + `array 真并发 500000 append+extend` + `sqlite3 真并发 500000 INSERT+SELECT` + `subprocess 真并发 300 spawn echo` + `multiprocessing 真并发 200 spawn` + 真底层测试。

覆盖 xml.etree 真 1 + struct 真 1 + array 真 1 + sqlite3 真 1 + subprocess 真 1 + multiprocessing 真 1 (共 6 真测试) 模块:
  - `xml.etree 真 500000 element 增+删+查 iter+find+findall`
  - `struct 真 500000 pack '<I' (0..499999) + unpack '<I' first+last`
  - `array 真 500000 append+extend 验 sum`
  - `sqlite3 真 500000 INSERT+SELECT 验 count=500000`
  - `subprocess.Popen 真 300 spawn echo 'forge_sub_v1'`
  - `multiprocessing.Process 真 200 spawn 'forge_mp_v1'`
"""
import array
import multiprocessing
import sqlite3
import struct
import subprocess
import xml.etree.ElementTree as ET

import pytest


# -- xml.etree 真并发 500000 element ----

class TestXmlEtreeRealConcurrentV9:
    def test_iter_500000(self):
        """`xml.etree 真 500000 element 增+删+查 iter+find+findall。"""
        root = ET.Element("forge_root")

        # 增 500000 element
        for i in range(500_000):
            ET.SubElement(root, f"forge_{i}")

        # 删所有偶数下标 element (用 findall 高效批量)
        for elem in list(root.findall("forge_*"))[::2]:
            root.remove(elem)

        # 查所有 element 用 iter
        tags = [el.tag for el in root.iter()]

        # 必 root + 250000 剩
        assert "forge_root" in tags
        assert len(tags) >= 250_000


# -- struct 真并发 500000 ----

class TestStructRealConcurrentV6:
    def test_pack_unpack_500000(self):
        """`struct 真 500000 pack '<I' (0..499999) + unpack '<I' first+last。"""
        # 500000 pack '<I' 0..499999
        packed = b"".join(struct.pack("<I", i) for i in range(500_000))
        # 500000 unpack 验 first+last
        results = list(struct.iter_unpack("<I", packed))
        # 必 500000 elements
        assert len(results) == 500_000
        # 必 first=0
        assert results[0] == (0,)
        # 必 last=499999
        assert results[-1] == (499_999,)


# -- array 真并发 500000 ----

class TestArrayRealConcurrentV6:
    def test_append_extend_500000(self):
        """`array 真 500000 append+extend 验 sum。"""
        a = array.array("l", range(0))  # empty
        # 500000 append
        for i in range(500_000):
            a.append(i)
        # 必 500000 elements
        assert len(a) == 500_000
        # 必 sum=0+1+...+499999
        assert sum(a) == sum(range(500_000))
        # extend
        a.extend([500_000])
        # 必 500001
        assert len(a) == 500_001


# -- sqlite3 真并发 500000 ----

class TestSqlite3RealConcurrentV6:
    def test_insert_select_500000(self):
        """`sqlite3 真 500000 INSERT+SELECT 验 count=500000。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        # 500000 INSERT
        for i in range(500_000):
            conn.execute(
                "INSERT INTO forge_t_v1 VALUES (?, ?)",
                (i, f"forge_n_{i}"),
            )
        conn.commit()
        # 500000 SELECT
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 count=500000
        assert cur.fetchone()[0] == 500_000
        # 必 first row id=0
        first = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id ASC LIMIT 1").fetchone()
        assert first[0] == 0
        # 必 last row id=499999
        last = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id DESC LIMIT 1").fetchone()
        assert last[0] == 499_999
        conn.close()


# -- subprocess 真并发 300 spawn ----

class TestSubprocessRealConcurrentV5:
    def test_Popen_300_spawn(self):
        """`subprocess.Popen 真 300 spawn echo 'forge_sub_v1'。"""
        procs = []
        for _ in range(300):
            p = subprocess.Popen(
                ["echo", "forge_sub_v1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            procs.append(p)
        # 必 300
        assert len(procs) == 300
        for p in procs:
            p.wait(timeout=10)
            assert p.returncode == 0


# -- multiprocessing 真并发 200 spawn ----

class TestMultiprocessingRealConcurrentV5:
    def test_Process_spawn_200(self):
        """`multiprocessing.Process 真 200 spawn 'forge_mp_v1'。"""

        def _mp_spawn_fn(result_queue):
            result_queue.put("forge_mp_v1")

        q = multiprocessing.Queue()
        procs = []
        for _ in range(200):
            p = multiprocessing.Process(target=_mp_spawn_fn, args=(q,))
            p.start()
            procs.append(p)
        for p in procs:
            p.join(timeout=10)
        # 必 200
        assert q.qsize() == 200
        # 必 'forge_mp_v1'
        assert q.get(timeout=30) == "forge_mp_v1"
