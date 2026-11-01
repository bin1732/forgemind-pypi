# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""shelve 模块的真实行为验证

覆盖模块:shelve(标准库),底层落在 dbm 的真实实现上

真实测试项(共 18 个):
   1. 写入后读回的值与写入内容一致
   2. 关闭后重新打开,键名与取值都还在
   3. in 判定区分已存键与缺失键
   4. get 对缺失键返回调用方给的默认值
   5. 读取缺失键抛 KeyError
   6. 同键重复写入后取到新值,键数量不变
   7. 删除键后数据库里不再有这个键
   8. 删除缺失键抛 KeyError
   9. 嵌套的 dict/list/tuple/None 原样往返
  10. 二进制值往返后逐字节相同
  11. 中文键名与中文取值原样存取
  12. 迭代产出全部键名
  13. items() 与 values() 给出键值对与取值
  14. writeback=True 时两次取值是同一对象,sync() 持久化就地修改
  15. writeback=False 时两次取值是不同对象,就地修改不落库
  16. flag='n' 打开的是全新空库
  17. flag='r' 打开不存在的数据库抛 dbm.error
  18. dbm.dumb 写出的库能被 shelve 打开并读出键值

数据库文件全部落在 tmp_path 下,读写都是真实 IO;某个 dbm 后端缺失时用
skipif 跳过,不做任何伪造。
"""

import dbm
import pickle
import shelve
from pathlib import Path

import pytest

try:  # pragma: no cover - 取决于解释器自带的 dbm 实现
    import dbm.dumb as _dbm_dumb
except ImportError:  # pragma: no cover - 没有 dumb 后端时跳过相关用例
    _dbm_dumb = None

_AVAILABLE_BACKENDS = []
for _backend_name in ("dbm.gnu", "dbm.ndbm", "dbm.dumb"):
    try:
        __import__(_backend_name)
    except ImportError:
        continue
    _AVAILABLE_BACKENDS.append(_backend_name)

pytestmark = pytest.mark.skipif(
    not _AVAILABLE_BACKENDS,
    reason="当前解释器没有可用的 dbm 后端",
)


def test_shelve_write_then_read_returns_stored_value(tmp_path: Path) -> None:
    """写入的字符串被原样读回,读到的值与写入内容完全一致。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["name"] = "forge"
    with shelve.open(str(path)) as shelf:
        assert shelf["name"] == "forge"


def test_shelve_reopen_keeps_all_keys_and_values(tmp_path: Path) -> None:
    """关闭后重新打开,三个键的键名、取值与键数量都保持一致。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["a"] = 1
        shelf["b"] = "two"
        shelf["c"] = 3.5
    with shelve.open(str(path)) as shelf:
        assert sorted(shelf.keys()) == ["a", "b", "c"]
        assert len(shelf) == 3
        assert shelf["a"] == 1
        assert shelf["b"] == "two"
        assert shelf["c"] == 3.5


def test_shelve_contains_reports_existing_and_missing_keys(tmp_path: Path) -> None:
    """in 判定对已存键为 True,对没有写过的键为 False。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["present"] = 1
        assert "present" in shelf
        assert "absent" not in shelf


def test_shelve_get_returns_default_for_missing_key(tmp_path: Path) -> None:
    """get 对缺失键返回调用方给的默认值,不抛异常。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["present"] = 1
        assert shelf.get("absent") is None
        assert shelf.get("absent", "default-value") == "default-value"
        assert shelf.get("present", "default-value") == 1


def test_shelve_missing_key_raises_key_error(tmp_path: Path) -> None:
    """读取没有写过的键抛 KeyError,异常信息里带键名。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["present"] = 1
        with pytest.raises(KeyError) as excinfo:
            shelf["absent"]
        assert "absent" in str(excinfo.value)


def test_shelve_overwrite_replaces_value_without_adding_key(tmp_path: Path) -> None:
    """同键重复写入后取到新值,键数量不增加。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["k"] = "first"
        shelf["k"] = "second"
        assert shelf["k"] == "second"
        assert len(shelf) == 1
        assert sorted(shelf.keys()) == ["k"]


def test_shelve_delete_removes_key_from_database(tmp_path: Path) -> None:
    """删除键后 in 判定为 False,重新打开数据库该键同样不存在。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["keep"] = 1
        shelf["drop"] = 2
        del shelf["drop"]
        assert "drop" not in shelf
        assert sorted(shelf.keys()) == ["keep"]
    with shelve.open(str(path)) as shelf:
        assert sorted(shelf.keys()) == ["keep"]
        assert "drop" not in shelf


def test_shelve_delete_missing_key_raises_key_error(tmp_path: Path) -> None:
    """删除没有写过的键抛 KeyError,异常信息里带键名。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["present"] = 1
        with pytest.raises(KeyError) as excinfo:
            del shelf["absent"]
        assert "absent" in str(excinfo.value)


def test_shelve_stores_nested_picklable_structures(tmp_path: Path) -> None:
    """嵌套的 dict/list/tuple/None 都能原样往返,类型与取值都不变。"""
    path = tmp_path / "shelf"
    payload = {"rows": [1, 2, 3], "meta": ("x", "y"), "flag": None}
    with shelve.open(str(path)) as shelf:
        shelf["payload"] = payload
    with shelve.open(str(path)) as shelf:
        stored = shelf["payload"]
        assert stored == payload
        assert stored["rows"] == [1, 2, 3]
        assert stored["meta"] == ("x", "y")
        assert stored["flag"] is None


def test_shelve_stores_bytes_unchanged(tmp_path: Path) -> None:
    """二进制值往返后逐字节相同,空字节与非 ASCII 字节都保真。"""
    path = tmp_path / "shelf"
    raw = b"\x00\x01\xff\xfe binary"
    with shelve.open(str(path)) as shelf:
        shelf["blob"] = raw
    with shelve.open(str(path)) as shelf:
        assert shelf["blob"] == raw
        assert len(shelf["blob"]) == len(raw)


def test_shelve_stores_unicode_keys_and_values(tmp_path: Path) -> None:
    """中文键名与中文取值原样存取,键名列表里也是中文。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["名称"] = "灵感引擎工坊"
    with shelve.open(str(path)) as shelf:
        assert shelf["名称"] == "灵感引擎工坊"
        assert list(shelf.keys()) == ["名称"]


def test_shelve_iteration_yields_every_key(tmp_path: Path) -> None:
    """迭代产出全部键名,数量与 len() 一致。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["a"] = 1
        shelf["b"] = 2
        shelf["c"] = 3
        assert sorted(iter(shelf)) == ["a", "b", "c"]
        assert len(list(iter(shelf))) == 3
        assert len(shelf) == 3


def test_shelve_items_and_values_return_stored_pairs(tmp_path: Path) -> None:
    """items() 给出键值对,values() 给出取值序列,内容与写入一致。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["a"] = 1
        shelf["b"] = "two"
        assert sorted(shelf.items()) == [("a", 1), ("b", "two")]
        assert sorted(shelf.values(), key=str) == [1, "two"]


def test_shelve_writeback_returns_same_object_and_persists_on_sync(tmp_path: Path) -> None:
    """writeback=True 时两次取值是同一对象,sync() 后就地修改被写回数据库。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path), writeback=True) as shelf:
        shelf["nums"] = [1, 2]
        first = shelf["nums"]
        second = shelf["nums"]
        assert first is second
        first.append(3)
        shelf.sync()
    with shelve.open(str(path)) as shelf:
        assert shelf["nums"] == [1, 2, 3]


def test_shelve_without_writeback_drops_in_place_mutation(tmp_path: Path) -> None:
    """writeback=False 时两次取值是不同对象,就地修改不进入数据库。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["nums"] = [1, 2]
        first = shelf["nums"]
        second = shelf["nums"]
        assert first is not second
        first.append(3)
    with shelve.open(str(path)) as shelf:
        assert shelf["nums"] == [1, 2]


def test_shelve_flag_n_creates_empty_database_over_existing(tmp_path: Path) -> None:
    """flag='n' 打开的是全新空库,原有的键全部消失。"""
    path = tmp_path / "shelf"
    with shelve.open(str(path)) as shelf:
        shelf["old"] = 1
    with shelve.open(str(path), flag="n") as shelf:
        assert sorted(shelf.keys()) == []
        assert len(shelf) == 0
    with shelve.open(str(path)) as shelf:
        assert sorted(shelf.keys()) == []


def test_shelve_flag_r_on_missing_file_raises_dbm_error(tmp_path: Path) -> None:
    """flag='r' 打开不存在的数据库抛 dbm.error,提示改用 c 或 n。"""
    with pytest.raises(dbm.error) as excinfo:
        shelve.open(str(tmp_path / "absent"), flag="r")
    assert "doesn't exist" in str(excinfo.value)


@pytest.mark.skipif(_dbm_dumb is None, reason="当前解释器没有 dbm.dumb 后端")
def test_shelve_reads_database_written_by_dumb_backend(tmp_path: Path) -> None:
    """dbm.dumb 存下 pickle 后的字节,shelve 能读出该值并继续往同一个库写。"""
    path = tmp_path / "dumb"
    with _dbm_dumb.open(str(path), "c") as raw:
        raw[b"key"] = pickle.dumps("value")
    assert dbm.whichdb(str(path)) == "dbm.dumb"
    with shelve.open(str(path)) as shelf:
        assert shelf["key"] == "value"
        shelf["extra"] = 2
    with shelve.open(str(path)) as shelf:
        assert sorted(shelf.keys()) == ["extra", "key"]
        assert shelf["extra"] == 2
