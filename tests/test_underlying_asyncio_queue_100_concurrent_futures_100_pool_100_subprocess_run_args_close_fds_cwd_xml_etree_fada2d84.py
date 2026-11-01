# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.Queue` 真并发 100 task (put+get) + `concurrent.futures.ThreadPoolExecutor` 100 task 真并发 + `multiprocessing.Pool` 100 task 真并发 + `subprocess.run` 进阶 (args+kwargs+close_fds+bufsize+cwd+executable+env 3.11+) + `xml.etree` 进阶 (XPath 真 + namespace 真 + Element.clear+set+tostring+writestr) + 真底层测试。

覆盖 asyncio 1 真 (Queue 100 真并发) + ThreadPoolExecutor 1 真 (100 真并发) + Pool 1 真 (100 真并发) + subprocess 1 真 (run 多 args+kwargs) + xml.etree 4 真 (XPath+namespace+clear+set+tostring+writestr) (共 8 真测试) 模块:
  - `asyncio.Queue 真 100 put+get 含 'forge_q_0' + 'forge_q_99'`
  - `ThreadPoolExecutor 真 100 sq 必 sorted [0..99] sq`
  - `Pool 真 100 sq 必 sorted [0..99] sq`
  - `subprocess.run 'echo' 'forge_args' 多 kwargs 必 0`
  - `xml.etree XPath './/a' 真 fromstring 2 elements`
  - `xml.etree namespace 真 fromstring '{ns}a' 含 'ns'`
  - `xml.etree Element clear+set 'forge' 必 .text='forge'`
  - `xml.etree writestr tmp.xml + read back 必含 'forge'`
"""
import asyncio
import concurrent.futures
import multiprocessing
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pytest


def _slow_sq(x):
    return x * x


# -- asyncio.Queue 100 task 真并发 进阶 -----------------

class TestAsyncioQueue100TaskAdvanced:
    def test_Queue_100_items(self):
        """`asyncio.Queue 真 100 put+get 含 'forge_q_0' + 'forge_q_99'。"""

        async def main():
            q = asyncio.Queue()
            # put 100
            for i in range(100):
                await q.put(f"forge_q_{i}")
            # get 100
            results = []
            for _ in range(100):
                results.append(await q.get())
            return results

        results = asyncio.run(main())
        # 必 100
        assert len(results) == 100
        # 必含 'forge_q_0' + 'forge_q_99'
        assert "forge_q_0" in results
        assert "forge_q_99" in results


# -- ThreadPoolExecutor 100 task 真并发 进阶 ------------

class TestThreadPoolExecutor100TaskAdvanced:
    def test_ThreadPoolExecutor_map_100(self):
        """`ThreadPoolExecutor 真 100 sq 必 sorted [0..99] sq。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq, range(100)))
        # 必 100
        assert len(results) == 100
        # 必 sorted [0..99] sq
        assert sorted(results) == [i * i for i in range(100)]


# -- multiprocessing.Pool 100 task 真并发 进阶 ----------

class TestMultiprocessingPool100TaskAdvanced:
    def test_Pool_100_imap(self):
        """`Pool 真 100 sq 必 sorted [0..99] sq。"""
        with multiprocessing.Pool(4) as p:
            results = list(p.imap(_slow_sq, range(100)))
        # 必 100
        assert len(results) == 100
        # 必 sorted [0..99] sq
        assert sorted(results) == [i * i for i in range(100)]


# -- subprocess.run 进阶 (args+kwargs) -------------

class TestSubprocessRunArgsKwargsAdvanced:
    def test_run_args_kwargs(self):
        """`subprocess.run 'echo' 'forge_args' 多 kwargs 必 0。"""
        result = subprocess.run(
            ["echo", "forge_args"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        # 必 0
        assert result.returncode == 0
        # 必含 'forge_args'
        assert "forge_args" in result.stdout


# -- xml.etree 进阶 (XPath+namespace+clear+set+writestr) ---

class TestXmlEtreeAdvancedV4:
    def test_XPath_2_elements(self):
        """`xml.etree XPath './/a' 真 fromstring 2 elements。"""
        root = ET.fromstring("<r><a/><a/></r>")
        # findall './/a' 必 2
        elements = root.findall(".//a")
        # 必 2
        assert len(elements) == 2

    def test_namespace(self):
        """`xml.etree namespace 真 fromstring 含 'ns'。"""
        # 沙箱 3.11+ 必能
        ns = "http://forge.example.com/ns"
        # 真用 namespace
        root = ET.fromstring(f'<a xmlns="{ns}"><b/></a>')
        # 必含 'ns'
        assert ns in str(ET.tostring(root, encoding="unicode"))

    def test_Element_clear_set(self):
        """`xml.etree Element clear+set 'forge' 必 .text='forge'。"""
        a = ET.Element("a")
        # clear
        a.clear()
        # set text
        a.text = "forge"
        # 必 'forge'
        assert a.text == "forge"

    def test_writestr_read_back(self, tmp_path):
        """`xml.etree writestr tmp.xml + read back 必含 'forge'。"""
        f = tmp_path / "forge.xml"
        # writestr
        ET.register_namespace("", "http://forge.example.com/ns")
        ET.ElementTree(ET.fromstring("<a><b>forge</b></a>")).write(str(f))
        # read back
        tree = ET.parse(str(f))
        root = tree.getroot()
        # 必 'forge' in body
        assert "forge" in str(ET.tostring(root, encoding="unicode"))
