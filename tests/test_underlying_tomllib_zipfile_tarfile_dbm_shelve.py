# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tomllib` + `zipfile` + `tarfile` + `dbm` + `shelve` 真底层测试。

覆盖格式/压缩/键值存储模块:
  - `tomllib.loads('key = "value"')` 真解 TOML 为 dict
  - `tomllib.loads('[section]\\nk = 42')` 真按 section 解析
  - `zipfile.ZipFile(..., 'w')` 真打包 + `ZipFile(..., 'r').read('name')` 拿回
  - `zipfile.ZipFile.namelist()` 真列已加条目
  - `tarfile.open(mode='w:gz')` 真打包 2 个文件,`mode='r:gz'` 读出
  - `dbm.dumb.open(tmp)` 真存 k/v,`b'key'` 拿到 `b'value'`
  - `shelve.open(tmp)` 真 dict-like 持久化,close 后重开数据还在
  - `mailbox.MH(tmp)` 真加一封邮件到序列号路径
"""
import dbm
import dbm.dumb
import gzip
import mailbox
import os
import shelve
import shutil
import sys
import tarfile
import tempfile
import tomllib
import zipfile

import pytest


# -- tomllib ------------------------------------------------------------------

class TestTomllib:
    def test_loads_simple_key_value(self):
        """`tomllib.loads('key = "value"')` 真解 TOML 为 dict。"""
        d = tomllib.loads('key = "forge"\n')
        assert d == {"key": "forge"}, f"应=单 key dict,实际 {d!r}"

    def test_loads_section_parsing(self):
        """`tomllib.loads('[s]\\nk = 42')` 真按 section 解析。"""
        d = tomllib.loads("[s]\nk = 42\nname = \"forge\"\n")
        assert d == {"s": {"k": 42, "name": "forge"}}, f"应=嵌套 dict,实际 {d!r}"

    def test_loads_array_of_tables(self):
        """`tomllib.loads('[[items]]\\nname = \"a\"\\n[[items]]\\nname = \"b\"')` 真解析为 list。"""
        src = '[[items]]\nname = "a"\n[[items]]\nname = "b"\n'
        d = tomllib.loads(src)
        assert d == {"items": [{"name": "a"}, {"name": "b"}]}, (
            f"应=array of tables,实际 {d!r}"
        )


# -- zipfile ------------------------------------------------------------------

class TestZipfile:
    def test_create_read_round_trip(self):
        """`zipfile.ZipFile(..., 'w')` 真打包 2 文件,`ZipFile(..., 'r')` 读出原字节。"""
        with tempfile.TemporaryDirectory() as d:
            zpath = os.path.join(d, "test.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("a.txt", b"alpha content")
                zf.writestr("b.txt", b"bravo content")
            assert os.path.isfile(zpath)
            with zipfile.ZipFile(zpath, "r") as zf:
                names = sorted(zf.namelist())
                assert names == ["a.txt", "b.txt"], f"namelist 应=['a','b'],实际 {names}"
                assert zf.read("a.txt") == b"alpha content"
                assert zf.read("b.txt") == b"bravo content"

    def test_zipfile_compresslevel_round_trip(self):
        """`zipfile.ZipFile(..., 'w', compresslevel=9)` + `writestr(..., ZIP_DEFLATED)` 真压缩。"""
        with tempfile.TemporaryDirectory() as d:
            zpath = os.path.join(d, "tight.zip")
            payload = b"forgemind " * 1000  # 10000 字节有重复模式
            with zipfile.ZipFile(zpath, "w", compresslevel=9) as zf:
                # 显式传 ZIP_DEFLATED,确保真压缩
                zf.writestr("data", payload, compress_type=zipfile.ZIP_DEFLATED)
            size = os.path.getsize(zpath)
            # 'forgemind ' 重复模式 DEFLATE 压缩后应明显小于原 10000
            assert size < 1000, f"压缩 10000 字节重复模式应 < 1000,实际 {size}"
            with zipfile.ZipFile(zpath, "r") as zf:
                assert zf.read("data") == payload

    def test_zipfile_infolist_has_metadata(self):
        """`ZipFile.infolist()` 真返 ZipInfo 含 filename/size/CRC。"""
        import binascii
        with tempfile.TemporaryDirectory() as d:
            zpath = os.path.join(d, "meta.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("hello", b"forge")
            with zipfile.ZipFile(zpath, "r") as zf:
                infos = zf.infolist()
                assert len(infos) == 1
                info = infos[0]
                assert info.filename == "hello"
                assert info.file_size == 5
                # CRC32 of "forge" 用 binascii 真算
                assert info.CRC == binascii.crc32(b"forge")


# -- tarfile ------------------------------------------------------------------

class TestTarfile:
    def test_create_gz_tar_round_trip(self):
        """`tarfile.open(mode='w:gz')` 真打包 + `mode='r:gz'` 读出。"""
        with tempfile.TemporaryDirectory() as d:
            tpath = os.path.join(d, "test.tar.gz")
            with tarfile.open(tpath, mode="w:gz") as tf:
                info = tarfile.TarInfo("first.txt")
                data = b"first content"
                info.size = len(data)
                tf.addfile(info, io_bytes(data))
                info2 = tarfile.TarInfo("second.txt")
                data2 = b"second content"
                info2.size = len(data2)
                tf.addfile(info2, io_bytes(data2))
            assert os.path.isfile(tpath)
            with tarfile.open(tpath, mode="r:gz") as tf:
                names = sorted(tf.getnames())
                assert names == ["first.txt", "second.txt"], (
                    f"应含 2 文件,实际 {names}"
                )
                f1 = tf.extractfile("first.txt")
                assert f1.read() == b"first content"

    def test_tarfile_iter_contains_files(self):
        """`tarfile.open(..., 'r').getmembers()` 真列 TarInfo list。"""
        with tempfile.TemporaryDirectory() as d:
            tpath = os.path.join(d, "x.tar")
            with tarfile.open(tpath, mode="w") as tf:
                info = tarfile.TarInfo("only.txt")
                info.size = 4
                tf.addfile(info, io_bytes(b"data"))
            with tarfile.open(tpath, mode="r") as tf:
                members = tf.getmembers()
                assert len(members) == 1
                assert members[0].name == "only.txt"
                assert members[0].size == 4


# -- dbm / shelve -------------------------------------------------------------

class TestDbmShelve:
    def test_dbm_dumb_round_trip(self):
        """`dbm.dumb.open(tmp)` 真存 k/v,`b'key'` 拿 `b'value'`。"""
        with tempfile.TemporaryDirectory() as d:
            dbpath = os.path.join(d, "forge.dbm")
            with dbm.dumb.open(dbpath, "c") as db:
                db[b"alpha"] = b"first"
                db[b"beta"] = b"second"
                assert db[b"alpha"] == b"first"
            # 重新打开,数据还在
            with dbm.dumb.open(dbpath, "r") as db:
                assert db[b"alpha"] == b"first"
                assert db[b"beta"] == b"second"
                assert b"alpha" in db
                assert b"missing" not in db

    def test_shelve_round_trip_across_close(self):
        """`shelve.open(tmp)` 真 dict-like 持久化,close 后重开数据还在。"""
        with tempfile.TemporaryDirectory() as d:
            spath = os.path.join(d, "forge.shelve")
            with shelve.open(spath) as db:
                db["k1"] = "v1"
                db["k2"] = [1, 2, 3]
            # 重新打开
            with shelve.open(spath) as db:
                assert db["k1"] == "v1"
                assert db["k2"] == [1, 2, 3]
                assert "k1" in db


# -- mailbox MH ---------------------------------------------------------------

class TestMailboxMH:
    def test_mh_add_message(self):
        """`mailbox.MH(tmp, create=True)` 真加一封邮件,flush 后序列号文件被创建。"""
        with tempfile.TemporaryDirectory() as d:
            mbox = mailbox.MH(d, create=True)
            try:
                msg = mailbox.mboxMessage()
                msg["Subject"] = "forge mh test"
                msg.set_payload("hello mh\n")
                key = mbox.add(msg)
                mbox.flush()  # 显式 flush 触发落盘
                # 序列号文件应被创建,名字以 key 开头
                files = os.listdir(d)
                mh_files = [f for f in files if f.startswith(str(key))]
                assert mh_files, (
                    f"目录应含以 {key} 开头的 MH 文件,实际 {files}"
                )
            finally:
                mbox.close()


# -- helper for tarfile.addfile ----------------------------------------------

import io as _io
def io_bytes(data: bytes) -> _io.BytesIO:
    return _io.BytesIO(data)
