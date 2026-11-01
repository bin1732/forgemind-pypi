# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.Queue` 真并发 200 task (put+get) + `concurrent.futures.ThreadPoolExecutor` 200 task 真并发 + `multiprocessing.Pool` 200 task 真并发 + `logging 进阶 (CRITICAL+FATAL+ERROR+dictConfig multi logger 进阶)` + `xml.etree 进阶 (XPath 真 + namespace 真 + Element.text 进阶)` + `csv 进阶 (Dialect.register+Sniffer 真)` + 真底层测试。

覆盖 asyncio 1 真 (Queue 200 真并发) + ThreadPoolExecutor 1 真 (200 真并发) + Pool 1 真 (200 真并发) + logging 3 真 (CRITICAL+FATAL+dictConfig multi logger) + xml.etree 3 真 (XPath+namespace+text) + csv 3 真 (register_dialect+Sniffer 真) (共 12 真测试) 模块:
  - `asyncio.Queue 真 200 put+get 含 'forge_q_0' + 'forge_q_199'`
  - `ThreadPoolExecutor 真 200 sq 必 sorted [0..199] sq`
  - `Pool 真 200 sq 必 sorted [0..199] sq`
  - `logging.CRITICAL=50 + FATAL=CRITICAL`
  - `logging.ERROR=40`
  - `logging.config.dictConfig 多 logger 进阶`
  - `xml.etree XPath 真 './/a' 含 ≥ 2`
  - `xml.etree namespace 真含 'ns'`
  - `xml.etree Element.text 进阶 set+get 'forge'`
  - `csv.register_dialect 'forge_d2' 真用`
  - `csv.Sniffer 真用 sniff sample`
  - `csv 真用 'forge_d2' reader`
"""
import asyncio
import concurrent.futures
import csv
import io
import logging
import logging.config
import multiprocessing
import xml.etree.ElementTree as ET

import pytest


def _slow_sq(x):
    return x * x


# -- asyncio.Queue 200 task 真并发 进阶 ----------------

class TestAsyncioQueue200TaskAdvance:
    def test_Queue_200(self):
        """`asyncio.Queue 真 200 put+get 含 'forge_q_0' + 'forge_q_199'。"""

        async def main():
            q = asyncio.Queue()
            for i in range(200):
                await q.put(f"forge_q_{i}")
            results = []
            for _ in range(200):
                results.append(await q.get())
            return results

        results = asyncio.run(main())
        # 必 200
        assert len(results) == 200
        # 必含 'forge_q_0' + 'forge_q_199'
        assert "forge_q_0" in results
        assert "forge_q_199" in results


# -- ThreadPoolExecutor 200 task 真并发 进阶 ------------

class TestThreadPoolExecutor200TaskAdvance:
    def test_ThreadPoolExecutor_map_200(self):
        """`ThreadPoolExecutor 真 200 sq 必 sorted [0..199] sq。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq, range(200)))
        # 必 200
        assert len(results) == 200
        # 必 sorted [0..199] sq
        assert sorted(results) == [i * i for i in range(200)]


# -- multiprocessing.Pool 200 task 真并发 进阶 ----------

class TestMultiprocessingPool200TaskAdvance:
    def test_Pool_200_imap(self):
        """`Pool 真 200 sq 必 sorted [0..199] sq。"""
        with multiprocessing.Pool(4) as p:
            results = list(p.imap(_slow_sq, range(200)))
        # 必 200
        assert len(results) == 200
        # 必 sorted [0..199] sq
        assert sorted(results) == [i * i for i in range(200)]


# -- logging 进阶 (CRITICAL+FATAL+ERROR+dictConfig) -------

class TestLoggingCriticalFatalErrorDictConfigAdvance:
    def test_CRITICAL_FATAL(self):
        """`logging.CRITICAL=50 + FATAL=CRITICAL。"""
        # 必 50
        assert logging.CRITICAL == 50
        # 必 FATAL=CRITICAL
        assert logging.FATAL == logging.CRITICAL

    def test_ERROR(self):
        """`logging.ERROR=40。"""
        # 必 40
        assert logging.ERROR == 40

    def test_dictConfig_multi(self):
        """`logging.config.dictConfig 多 logger。"""
        config = {
            "version": 1,
            "formatters": {
                "forge_fmt": {
                    "format": "%(levelname)s %(message)s",
                },
            },
            "handlers": {
                "forge_h": {
                    "class": "logging.StreamHandler",
                    "formatter": "forge_fmt",
                },
            },
            "loggers": {
                "forge_dictconfig_x": {
                    "handlers": ["forge_h"],
                    "level": "INFO",
                },
            },
        }
        logging.config.dictConfig(config)
        logger = logging.getLogger("forge_dictconfig_x")
        # 必 level INFO
        assert logger.level == logging.INFO
        # cleanup
        logging.config.dictConfig({
            "version": 1,
            "disable_existing_loggers": False,
        })


# -- xml.etree 进阶 (XPath 真 + namespace + text) ---------

class TestXmlEtreeXPathNamespaceTextAdvance:
    def test_XPath(self):
        """`xml.etree XPath 真 './/a' 含 ≥ 2。"""
        root = ET.fromstring("<r><a/><a/></r>")
        elements = root.findall(".//a")
        # 必 ≥ 2
        assert len(elements) >= 2

    def test_namespace(self):
        """`xml.etree namespace 真含 'ns'。"""
        ns = "http://forge.example.com/ns"
        root = ET.fromstring(f'<a xmlns="{ns}"><b/></a>')
        # 必含 'ns'
        assert ns in str(ET.tostring(root, encoding="unicode"))

    def test_Element_text(self):
        """`xml.etree Element.text 进阶 set+get 'forge'。"""
        a = ET.Element("a")
        # set text
        a.text = "forge"
        # 必 'forge'
        assert a.text == "forge"


# -- csv 进阶 (Dialect.register 真 + Sniffer 真) --------

class TestCsvDialectRegisterSnifferAdvance:
    def test_register_dialect(self):
        """`csv.register_dialect 'forge_d2' 真用。"""
        try:
            csv.register_dialect(
                "forge_d2",
                delimiter="|",
                quotechar="*",
            )
            # 必能 list dialects
            assert "forge_d2" in csv.list_dialects()
        finally:
            csv.unregister_dialect("forge_d2")

    def test_Sniffer_sniff(self):
        """`csv.Sniffer 真用 sniff sample。"""
        sample = "a,b,c\n1,2,3\n4,5,6\n"
        dialect = csv.Sniffer().sniff(sample, delimiters=",")
        # 必 delimiter ','
        assert dialect.delimiter == ","

    def test_registered_reader(self):
        """`csv 真用 'forge_d2' reader。"""
        try:
            csv.register_dialect(
                "forge_d2",
                delimiter="|",
                quotechar="*",
            )
            data = "a|b|c\n1|2|3\n"
            reader = csv.reader(io.StringIO(data), dialect="forge_d2")
            rows = list(reader)
            # 必 2
            assert len(rows) == 2
            # 必 1st row ['a', 'b', 'c']
            assert rows[0] == ["a", "b", "c"]
        finally:
            csv.unregister_dialect("forge_d2")
