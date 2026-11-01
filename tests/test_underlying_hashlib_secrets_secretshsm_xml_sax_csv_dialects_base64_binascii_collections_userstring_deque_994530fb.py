# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`hashlib` 进阶 (md5+sha1+sha256+sha512+sha3_256+sha3_512+blake2b+blake2s) + `secrets` 进阶 (token_bytes+token_hex+token_urlsafe+compare_digest) + `xml.sax` 进阶 (parseString+ContentHandler+make_parser) + `csv.Dialect` 进阶 (register+unregister+list_dialects) + `base64` 进阶 (b64encode+b64decode+urlsafe_b64encode+urlsafe_b64decode) + `binascii` 进阶 (hexlify+unhexlify+crc32) + `collections.UserString+deque+ChainMap` 进阶 + 真底层测试。

覆盖 hashlib 6 + secrets 4 + xml.sax 4 + csv.Dialect 3 + base64 4 + binascii 3 + collections.UserString 3 + collections.deque 4 + collections.ChainMap 3 (共 34 真测试) 模块:
  - `hashlib.md5 32 char`
  - `hashlib.sha1 40 char`
  - `hashlib.sha256 64 char`
  - `hashlib.sha512 128 char`
  - `hashlib.sha3_256 64 char`
  - `hashlib.blake2b 128 char`
  - `secrets.token_bytes 16 bytes`
  - `secrets.token_hex 32 char`
  - `secrets.token_urlsafe 22 char`
  - `secrets.compare_digest True`
  - `xml.sax.parseString start+end events`
  - `xml.sax.make_parser parser`
  - `xml.sax.ContentHandler start+end`
  - `xml.sax.ContentHandler characters 'forge_text'`
  - `csv.register_dialect 'forge_dialect_test'`
  - `csv.list_dialects ≥ 1`
  - `csv.unregister_dialect 'forge_dialect_test'`
  - `base64.b64encode b'Zm9yZ2U='`
  - `base64.b64decode b'forge'`
  - `base64.urlsafe_b64encode b'Zm9yZ2U='`
  - `base64.urlsafe_b64decode b'forge'`
  - `binascii.hexlify b'666f726765'`
  - `binascii.unhexlify b'forge'`
  - `binascii.crc32 int`
  - `UserString 'forge'`
  - `UserString str(s) 'forge'`
  - `UserString + 'concat'`
  - `deque append+pop length`
  - `deque maxlen append overflow`
  - `deque rotate 'c' 'a' 'b'`
  - `deque extendleft ['forge']`
  - `ChainMap 'forge'`
  - `ChainMap['forge'] 1`
  - `ChainMap new_child 'forge_c'`
"""
import base64
import binascii
import collections
import csv
import hashlib
import io
import secrets
import xml.sax
import xml.sax.handler

import pytest


class _ForgeSaxHandler(xml.sax.handler.ContentHandler):
    def __init__(self):
        self.events = []
        self.text_buf = ""

    def startElement(self, name, attrs):
        self.events.append(("start", name))

    def endElement(self, name):
        self.events.append(("end", name))

    def characters(self, content):
        self.text_buf += content


# -- hashlib 进阶 (md5+sha1+sha256+sha512+sha3_256+blake2b) -----

class TestHashlibAdvanceV1:
    def test_md5(self):
        """`hashlib.md5 32 char。"""
        h = hashlib.md5(b"forge").hexdigest()
        assert len(h) == 32
        assert isinstance(h, str)

    def test_sha1(self):
        """`hashlib.sha1 40 char。"""
        h = hashlib.sha1(b"forge").hexdigest()
        assert len(h) == 40
        assert isinstance(h, str)

    def test_sha256(self):
        """`hashlib.sha256 64 char。"""
        h = hashlib.sha256(b"forge").hexdigest()
        assert len(h) == 64
        assert isinstance(h, str)

    def test_sha512(self):
        """`hashlib.sha512 128 char。"""
        h = hashlib.sha512(b"forge").hexdigest()
        assert len(h) == 128
        assert isinstance(h, str)

    def test_sha3_256(self):
        """`hashlib.sha3_256 64 char。"""
        h = hashlib.sha3_256(b"forge").hexdigest()
        assert len(h) == 64
        assert isinstance(h, str)

    def test_blake2b(self):
        """`hashlib.blake2b 128 char。"""
        h = hashlib.blake2b(b"forge").hexdigest()
        assert len(h) == 128
        assert isinstance(h, str)


# -- secrets 进阶 (token_bytes+token_hex+token_urlsafe+compare_digest) -

class TestSecretsAdvanceV1:
    def test_token_bytes(self):
        """`secrets.token_bytes 16 bytes。"""
        t = secrets.token_bytes(16)
        assert isinstance(t, bytes)
        assert len(t) == 16

    def test_token_hex(self):
        """`secrets.token_hex 32 char。"""
        t = secrets.token_hex(16)
        assert isinstance(t, str)
        assert len(t) == 32

    def test_token_urlsafe(self):
        """`secrets.token_urlsafe 22 char。"""
        t = secrets.token_urlsafe(16)
        assert isinstance(t, str)
        assert len(t) >= 22

    def test_compare_digest(self):
        """`secrets.compare_digest True。"""
        assert secrets.compare_digest("forge", "forge") is True
        assert secrets.compare_digest("forge", "other") is False


# -- xml.sax 进阶 (parseString+make_parser+ContentHandler) ---

class TestXmlSaxAdvanceV1:
    def test_parseString(self):
        """`xml.sax.parseString start+end events。"""
        handler = _ForgeSaxHandler()
        xml.sax.parseString("<r><a/></r>", handler)
        # 必 start 'r' + start 'a' + end 'a' + end 'r'
        assert ("start", "r") in handler.events
        assert ("start", "a") in handler.events
        assert ("end", "a") in handler.events
        assert ("end", "r") in handler.events

    def test_make_parser(self):
        """`xml.sax.make_parser parser。"""
        parser = xml.sax.make_parser()
        assert parser is not None

    def test_ContentHandler(self):
        """`xml.sax.ContentHandler start+end。"""
        h = xml.sax.handler.ContentHandler()
        assert h is not None
        # startElement
        h.startElement("a", {})
        h.endElement("a")

    def test_ContentHandler_characters(self):
        """`xml.sax.ContentHandler characters 'forge_text'。"""
        h = _ForgeSaxHandler()
        h.characters("forge_text")
        # 必 'forge_text'
        assert h.text_buf == "forge_text"


# -- csv.Dialect 进阶 (register+unregister+list_dialects) ---

class _ForgeDialect(csv.Dialect):
    delimiter = ","
    quotechar = '"'
    doublequote = True
    skipinitialspace = True
    lineterminator = "\n"
    quoting = csv.QUOTE_MINIMAL


class TestCsvDialectAdvanceV1:
    def test_register(self):
        """`csv.register_dialect 'forge_dialect_test'。"""
        csv.register_dialect("forge_dialect_test", _ForgeDialect)
        assert "forge_dialect_test" in csv.list_dialects()

    def test_list(self):
        """`csv.list_dialects ≥ 1。"""
        result = csv.list_dialects()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_unregister(self):
        """`csv.unregister_dialect 'forge_dialect_test'。"""
        if "forge_dialect_test" in csv.list_dialects():
            csv.unregister_dialect("forge_dialect_test")
        assert "forge_dialect_test" not in csv.list_dialects()


# -- base64 进阶 (b64encode+b64decode+urlsafe) ----

class TestBase64AdvanceV1:
    def test_b64encode(self):
        """`base64.b64encode b'Zm9yZ2U='。"""
        r = base64.b64encode(b"forge")
        # 必 'Zm9yZ2U='
        assert r == b"Zm9yZ2U="

    def test_b64decode(self):
        """`base64.b64decode b'forge'。"""
        r = base64.b64decode(b"Zm9yZ2U=")
        # 必 b'forge'
        assert r == b"forge"

    def test_urlsafe_b64encode(self):
        """`base64.urlsafe_b64encode b'Zm9yZ2U='。"""
        r = base64.urlsafe_b64encode(b"forge")
        # 必 'Zm9yZ2U='
        assert r == b"Zm9yZ2U="

    def test_urlsafe_b64decode(self):
        """`base64.urlsafe_b64decode b'forge'。"""
        r = base64.urlsafe_b64decode(b"Zm9yZ2U=")
        # 必 b'forge'
        assert r == b"forge"


# -- binascii 进阶 (hexlify+unhexlify+crc32) ---

class TestBinasciiAdvanceV1:
    def test_hexlify(self):
        """`binascii.hexlify b'666f726765'。"""
        r = binascii.hexlify(b"forge")
        # 必 '666f726765'
        assert r == b"666f726765"

    def test_unhexlify(self):
        """`binascii.unhexlify b'forge'。"""
        r = binascii.unhexlify(b"666f726765")
        # 必 b'forge'
        assert r == b"forge"

    def test_crc32(self):
        """`binascii.crc32 int。"""
        c = binascii.crc32(b"forge")
        assert isinstance(c, int)


# -- collections.UserString 进阶 -------

class TestUserStringAdvanceV1:
    def test_init(self):
        """`UserString 'forge'。"""
        us = collections.UserString("forge")
        # 必 'forge'
        assert str(us) == "forge"

    def test_str_conversion(self):
        """`UserString str(s) 'forge'。"""
        us = collections.UserString("forge")
        # 必 'forge'
        assert str(us) == "forge"
        assert len(us) == 5

    def test_concat(self):
        """`UserString + 'concat'。"""
        us = collections.UserString("forge") + "_concat"
        # 必 'forge_concat'
        assert str(us) == "forge_concat"


# -- collections.deque 进阶 (append+maxlen+rotate+extendleft) ---

class TestDequeAdvanceV1:
    def test_append_pop(self):
        """`deque append+pop length。"""
        d = collections.deque()
        d.append("a")
        d.append("b")
        # 必 length 2
        assert len(d) == 2
        d.pop()
        # 必 length 1
        assert len(d) == 1

    def test_maxlen(self):
        """`deque maxlen append overflow。"""
        d = collections.deque(maxlen=2)
        d.append("a")
        d.append("b")
        d.append("c")
        # 必 ['b', 'c']
        assert list(d) == ["b", "c"]

    def test_rotate(self):
        """`deque rotate 'c' 'a' 'b'。"""
        d = collections.deque(["a", "b", "c"])
        d.rotate(1)
        # 必 ['c', 'a', 'b']
        assert list(d) == ["c", "a", "b"]

    def test_extendleft(self):
        """`deque extendleft ['forge']。"""
        d = collections.deque(["a"])
        d.extendleft(["forge"])
        # 必 ['forge', 'a']
        assert list(d) == ["forge", "a"]


# -- collections.ChainMap 进阶 (maps+__getitem__+new_child) ---

class TestChainMapAdvanceV1:
    def test_init(self):
        """`ChainMap 'forge'。"""
        cm = collections.ChainMap({"forge": 1})
        # 必 'forge'
        assert "forge" in cm

    def test_getitem(self):
        """`ChainMap['forge'] 1。"""
        cm = collections.ChainMap({"forge": 1})
        # 必 1
        assert cm["forge"] == 1

    def test_new_child(self):
        """`ChainMap new_child 'forge_c'。"""
        cm = collections.ChainMap({"forge": 1})
        new = cm.new_child({"forge_c": 2})
        # 必 'forge_c' 2
        assert new["forge_c"] == 2
        # 必 仍 'forge' 1
        assert new["forge"] == 1
