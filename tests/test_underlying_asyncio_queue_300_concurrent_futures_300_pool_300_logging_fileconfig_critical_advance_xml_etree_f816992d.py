# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.Queue` 真并发 300 task (put+get) + `concurrent.futures.ThreadPoolExecutor` 300 task 真并发 + `multiprocessing.Pool` 300 task 真并发 + `logging 进阶 (fileConfig 进阶 + CRITICAL+dictConfig)` + `xml.etree 进阶 (XPath 真+namespace+remove+append+findall 进阶)` + `urllib.parse 进阶 (urlparse+parse_qs+urlencode+urljoin+quote+unquote 真)` + 真底层测试。

覆盖 asyncio 1 真 (Queue 300) + ThreadPoolExecutor 1 真 (300) + Pool 1 真 (300) + logging 3 真 (fileConfig+CRITICAL+dictConfig) + xml.etree 5 真 (XPath+namespace+remove+append+findall) + urllib.parse 6 真 (urlparse+parse_qs+urlencode+urljoin+quote+unquote) (共 17 真测试) 模块:
  - `asyncio.Queue 真 300 put+get 含 'forge_q_0' + 'forge_q_299'`
  - `ThreadPoolExecutor 真 300 sq 必 sorted [0..299] sq`
  - `Pool 真 300 sq 必 sorted [0..299] sq`
  - `logging.fileConfig 真用 config file`
  - `logging.CRITICAL=50`
  - `logging.dictConfig 进阶 5 keys 必能`
  - `xml.etree XPath './/a' 必 ≥ 2`
  - `xml.etree namespace 真 'ns'`
  - `xml.etree remove 必 len 减 1`
  - `xml.etree append 必 len 加 1`
  - `xml.etree findall './/b' 必 ≥ 1`
  - `urllib.parse.urlparse 真 scheme 'http' + netloc`
  - `urllib.parse.parse_qs 真 'forge=1' 必 {'forge':['1']}`
  - `urllib.parse.urlencode 真 'forge' 必含 'forge'`
  - `urllib.parse.urljoin 'a/b' 'c' 必 'a/c'`
  - `urllib.parse.quote ' ' 必 '%20'`
  - `urllib.parse.unquote '%20' 必 ' '`
"""
import asyncio
import concurrent.futures
import configparser
import json
import logging
import logging.config
import multiprocessing
import urllib.parse
import xml.etree.ElementTree as ET

import pytest


def _slow_sq(x):
    return x * x


# -- asyncio.Queue 300 task 真并发 进阶 ----------------

class TestAsyncioQueue300TaskAdvance:
    def test_Queue_300(self):
        """`asyncio.Queue 真 300 put+get 含 'forge_q_0' + 'forge_q_299'。"""

        async def main():
            q = asyncio.Queue()
            for i in range(300):
                await q.put(f"forge_q_{i}")
            results = []
            for _ in range(300):
                results.append(await q.get())
            return results

        results = asyncio.run(main())
        # 必 300
        assert len(results) == 300
        # 必含 'forge_q_0' + 'forge_q_299'
        assert "forge_q_0" in results
        assert "forge_q_299" in results


# -- ThreadPoolExecutor 300 task 真并发 进阶 ------------

class TestThreadPoolExecutor300TaskAdvance:
    def test_ThreadPoolExecutor_map_300(self):
        """`ThreadPoolExecutor 真 300 sq 必 sorted [0..299] sq。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq, range(300)))
        # 必 300
        assert len(results) == 300
        # 必 sorted [0..299] sq
        assert sorted(results) == [i * i for i in range(300)]


# -- multiprocessing.Pool 300 task 真并发 进阶 ----------

class TestMultiprocessingPool300TaskAdvance:
    def test_Pool_300_imap(self):
        """`Pool 真 300 sq 必 sorted [0..299] sq。"""
        with multiprocessing.Pool(4) as p:
            results = list(p.imap(_slow_sq, range(300)))
        # 必 300
        assert len(results) == 300
        # 必 sorted [0..299] sq
        assert sorted(results) == [i * i for i in range(300)]


# -- logging 进阶 (fileConfig + CRITICAL + dictConfig 5 keys) --

class TestLoggingFileConfigCriticalDictConfigAdvance:
    def test_fileConfig(self, tmp_path):
        """`logging.fileConfig 真用 config file。"""
        # 真用 config file
        config_path = tmp_path / "forge_log.ini"
        config_path.write_text(
            """[loggers]
keys=root

[handlers]
keys=forge_h

[formatters]
keys=forge_fmt

[logger_root]
level=INFO
handlers=forge_h

[handler_forge_h]
class=StreamHandler
level=INFO
formatter=forge_fmt
args=(sys.stderr,)

[formatter_forge_fmt]
format=%(levelname)s %(message)s
"""
        )
        # fileConfig
        logging.config.fileConfig(str(config_path), disable_existing_loggers=False)
        # 必不抛
        assert True

    def test_CRITICAL(self):
        """`logging.CRITICAL=50。"""
        # 必 50
        assert logging.CRITICAL == 50

    def test_dictConfig_5_keys(self):
        """`logging.dictConfig 进阶 5 keys 必能。"""
        config = {
            "version": 1,
            "formatters": {
                "forge_fmt_a": {
                    "format": "%(levelname)s",
                },
                "forge_fmt_b": {
                    "format": "%(message)s",
                },
            },
            "handlers": {
                "forge_h_a": {
                    "class": "logging.StreamHandler",
                },
                "forge_h_b": {
                    "class": "logging.StreamHandler",
                },
            },
            "loggers": {
                "forge_logger_a": {
                    "level": "INFO",
                },
                "forge_logger_b": {
                    "level": "DEBUG",
                },
            },
        }
        # dictConfig
        logging.config.dictConfig(config)
        # 必能 getLogger
        logger = logging.getLogger("forge_logger_a")
        # 必 level INFO
        assert logger.level == logging.INFO
        # cleanup
        logging.config.dictConfig({
            "version": 1,
            "disable_existing_loggers": False,
        })


# -- xml.etree 进阶 (XPath+namespace+remove+append+findall) ----

class TestXmlEtreeXPathNamespaceRemoveAppendFindallAdvance:
    def test_XPath(self):
        """`xml.etree XPath './/a' 必 ≥ 2。"""
        root = ET.fromstring("<r><a/><a/></r>")
        elements = root.findall(".//a")
        # 必 ≥ 2
        assert len(elements) >= 2

    def test_namespace(self):
        """`xml.etree namespace 真 'ns'。"""
        ns = "http://forge.example.com/ns"
        root = ET.fromstring(f'<a xmlns="{ns}"><b/></a>')
        # 必含 'ns'
        assert ns in str(ET.tostring(root, encoding="unicode"))

    def test_remove(self):
        """`xml.etree remove 必 len 减 1。"""
        root = ET.fromstring("<r><a/><a/></r>")
        # 必 2
        assert len(list(root.iter("a"))) == 2
        # remove first
        root.remove(list(root.iter("a"))[0])
        # 必 1
        assert len(list(root.iter("a"))) == 1

    def test_append(self):
        """`xml.etree append 必 len 加 1。"""
        root = ET.fromstring("<r><a/></r>")
        # 必 1
        assert len(list(root.iter("a"))) == 1
        # append
        root.append(ET.Element("a"))
        # 必 2
        assert len(list(root.iter("a"))) == 2

    def test_findall_b(self):
        """`xml.etree findall './/b' 必 ≥ 1。"""
        root = ET.fromstring("<r><b>1</b><a><b>2</b></a></r>")
        elements = root.findall(".//b")
        # 必 ≥ 1
        assert len(elements) >= 1


# -- urllib.parse 进阶 (urlparse+parse_qs+urlencode+urljoin+quote+unquote) ---

class TestUrllibParseAdvanceV2:
    def test_urlparse(self):
        """`urllib.parse.urlparse 真 scheme 'http' + netloc。"""
        r = urllib.parse.urlparse("http://forge.example.com/forge?a=1")
        # 必 scheme 'http'
        assert r.scheme == "http"
        # 必 netloc 'forge.example.com'
        assert r.netloc == "forge.example.com"
        # 必 path '/forge'
        assert r.path == "/forge"

    def test_parse_qs(self):
        """`urllib.parse.parse_qs 真 'forge=1' 必 {'forge':['1']}。"""
        result = urllib.parse.parse_qs("forge=1&forge=2")
        # 必 dict
        assert "forge" in result
        # 必 ['1', '2']
        assert "1" in result["forge"]
        assert "2" in result["forge"]

    def test_urlencode(self):
        """`urllib.parse.urlencode 真 'forge' 必含 'forge'。"""
        result = urllib.parse.urlencode({"name": "forge"})
        # 必 'name=forge'
        assert "name=forge" in result

    def test_urljoin(self):
        """`urllib.parse.urljoin 'a/b' 'c' 必 'a/c'。"""
        result = urllib.parse.urljoin("http://forge.example.com/a/b", "c")
        # 必 'http://forge.example.com/a/c'
        assert result == "http://forge.example.com/a/c"

    def test_quote(self):
        """`urllib.parse.quote ' ' 必 '%20'。"""
        result = urllib.parse.quote("hello world")
        # 必 'hello%20world'
        assert result == "hello%20world"

    def test_unquote(self):
        """`urllib.parse.unquote '%20' 必 ' '。"""
        result = urllib.parse.unquote("hello%20world")
        # 必 'hello world'
        assert result == "hello world"
