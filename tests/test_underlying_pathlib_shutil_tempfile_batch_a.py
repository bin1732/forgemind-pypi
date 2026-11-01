# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""pathlib 基础行为验证:路径拼装、名称推导、目录遍历与文件读写全部落在真实文件系统上。

覆盖模块:pathlib(标准库)

真测试项(17 个):
  1. joinpath 与 / 运算符、os.path.join 产出同一条路径
  2. parent 与 parents 链对应磁盘上真实存在的目录层级
  3. stem / suffix / suffixes 对多种文件名的拆分结果
  4. with_name 只替换最后一段,根路径换名抛出 ValueError
  5. with_suffix 替换后缀、清空后缀、非法后缀三种不同结果
  6. resolve 解析出磁盘上已存在的绝对路径
  7. resolve(strict=True) 对缺失路径抛出 FileNotFoundError
  8. exists / is_file / is_dir 区分文件、目录与缺失条目
  9. iterdir 列出目录内真实条目并可读回内容
 10. glob 按模式命中预期文件名
 11. rglob 命中嵌套子目录中的文件
 12. stat 报出真实字节数与修改时间
 13. unlink 删除文件,对已删除路径再次删除抛 FileNotFoundError
 14. mkdir 的 parents / exist_ok 组合行为
 15. rename 移动文件、replace 覆盖目标文件后的字节结果
 16. write_text / read_text 的 UTF-8 往返
 17. write_bytes / read_bytes 的逐字节保真
"""

import os
import stat
from pathlib import Path

import pytest


def test_path_joinpath_and_operators_produce_same_path(tmp_path):
    """joinpath("b", "c.txt")、/ 运算符与 os.path.join 三种写法产出完全相同的路径串。"""
    base = tmp_path / "alpha"
    joined = base.joinpath("beta", "gamma.txt")
    divided = base / "beta" / "gamma.txt"
    os_joined = Path(os.path.join(str(base), "beta", "gamma.txt"))

    assert joined == divided == os_joined
    assert str(joined) == str(divided) == str(os_joined)
    assert joined.name == "gamma.txt"
    assert joined.parts[-2:] == ("beta", "gamma.txt")
    assert joined.suffix == ".txt"


def test_path_parent_chain_follows_real_directory_levels(tmp_path):
    """parent 指向文件所在的真实目录,parents 逐级向上直到 tmp_path,每一级都确实存在。"""
    level_one = tmp_path / "d1"
    level_two = level_one / "d2"
    level_two.mkdir(parents=True)
    target = level_two / "leaf.txt"
    target.write_bytes(b"leaf")

    assert target.parent == level_two
    assert target.parent.is_dir()
    assert target.parents[0] == level_two
    assert target.parents[1] == level_one
    assert target.parents[2] == tmp_path
    assert target.parents[0].name == "d2"
    assert target.parents[1].name == "d1"


def test_path_stem_suffix_and_suffixes_split_names(tmp_path):
    """多段后缀名的 stem/suffix/suffixes 取值确定,无后缀名与隐藏名都得到空后缀。"""
    archive = tmp_path / "archive.tar.gz"
    plain = tmp_path / "README"
    hidden = tmp_path / ".env"

    assert archive.stem == "archive.tar"
    assert archive.suffix == ".gz"
    assert archive.suffixes == [".tar", ".gz"]
    assert plain.stem == "README"
    assert plain.suffix == ""
    assert plain.suffixes == []
    assert hidden.stem == ".env"
    assert hidden.suffix == ""
    assert hidden.suffixes == []


def test_path_with_name_replaces_only_final_component(tmp_path):
    """with_name 换掉文件名但保留父目录;对根路径换名时抛出 ValueError 并提示空名字。"""
    source = tmp_path / "old.txt"
    replaced = source.with_name("new.md")

    assert replaced.name == "new.md"
    assert replaced.parent == tmp_path
    assert replaced.parent == source.parent
    assert source.name == "old.txt"

    with pytest.raises(ValueError, match="empty name"):
        Path("/").with_name("anything")


def test_path_with_suffix_replaces_clears_and_rejects_suffix(tmp_path):
    """with_suffix(".csv") 换后缀、with_suffix("") 清后缀,不带点的后缀触发 ValueError。"""
    source = tmp_path / "data.txt"

    assert source.with_suffix(".csv").name == "data.csv"
    assert source.with_suffix(".csv").parent == tmp_path
    assert source.with_suffix("").name == "data"
    assert source.name == "data.txt"

    with pytest.raises(ValueError, match="Invalid suffix"):
        source.with_suffix("csv")


def test_path_resolve_returns_existing_absolute_path(tmp_path):
    """resolve 把相对写法解析成磁盘上真实存在的绝对路径,解析结果与原路径指向同一文件。"""
    target = tmp_path / "real.txt"
    target.write_bytes(b"resolved-bytes")
    resolved = target.resolve()

    assert resolved.is_absolute()
    assert resolved == target
    assert resolved.exists()
    assert resolved.read_bytes() == b"resolved-bytes"


def test_path_resolve_strict_raises_for_missing_path(tmp_path):
    """strict=True 解析缺失路径抛 FileNotFoundError;strict=False 返回绝对路径但文件仍不存在。"""
    missing = tmp_path / "absent" / "nope.txt"

    with pytest.raises(FileNotFoundError, match="No such file or directory"):
        missing.resolve(strict=True)

    lenient = missing.resolve(strict=False)
    assert lenient.is_absolute()
    assert lenient == missing
    assert not lenient.exists()


def test_path_exists_is_file_is_dir_distinguish_real_entries(tmp_path):
    """exists / is_file / is_dir 对真实文件、真实目录、缺失路径给出互不相同的真假组合。"""
    real_file = tmp_path / "data.bin"
    real_file.write_bytes(b"\x00\x01")
    real_dir = tmp_path / "subdir"
    real_dir.mkdir()
    absent = tmp_path / "not-there"

    assert real_file.exists() is True
    assert real_file.is_file() is True
    assert real_file.is_dir() is False
    assert real_dir.exists() is True
    assert real_dir.is_dir() is True
    assert real_dir.is_file() is False
    assert absent.exists() is False
    assert absent.is_file() is False
    assert absent.is_dir() is False
    assert stat.S_ISREG(real_file.stat().st_mode)


def test_path_iterdir_lists_real_entries(tmp_path):
    """iterdir 列出的条目名与磁盘上真实文件一一对应,条目内容可以原样读回。"""
    (tmp_path / "a.txt").write_bytes(b"aaa")
    (tmp_path / "b.txt").write_bytes(b"bb")
    (tmp_path / "c.bin").write_bytes(b"c")

    entries = {entry.name: entry for entry in tmp_path.iterdir()}

    assert sorted(entries) == ["a.txt", "b.txt", "c.bin"]
    assert entries["a.txt"].read_bytes() == b"aaa"
    assert entries["b.txt"].read_bytes() == b"bb"
    assert entries["c.bin"].read_bytes() == b"c"
    assert all(entry.is_file() for entry in entries.values())


def test_path_glob_selects_expected_names(tmp_path):
    """glob("*.txt") 只命中 txt 文件,glob("*.bin") 命中另一种扩展名,两者互不重叠。"""
    (tmp_path / "one.txt").write_bytes(b"1")
    (tmp_path / "two.txt").write_bytes(b"2")
    (tmp_path / "three.bin").write_bytes(b"3")

    txt_names = sorted(path.name for path in tmp_path.glob("*.txt"))
    bin_names = sorted(path.name for path in tmp_path.glob("*.bin"))

    assert txt_names == ["one.txt", "two.txt"]
    assert bin_names == ["three.bin"]
    assert set(txt_names).isdisjoint(bin_names)
    assert (tmp_path / "one.txt").read_bytes() == b"1"


def test_path_rglob_matches_nested_files(tmp_path):
    """rglob 递归命中子目录里的文件,相对路径与写入位置逐个对齐。"""
    (tmp_path / "top.txt").write_bytes(b"top")
    nested = tmp_path / "mid" / "deep"
    nested.mkdir(parents=True)
    (nested / "bottom.txt").write_bytes(b"bottom")

    found = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*.txt"))

    assert found == ["mid/deep/bottom.txt", "top.txt"]
    assert (tmp_path / "mid" / "deep" / "bottom.txt").read_bytes() == b"bottom"


def test_path_stat_reports_size_and_mtime_of_real_file(tmp_path):
    """stat 报出的 st_size 等于落盘字节数,st_mtime 为正数并与 os.stat 的结果一致。"""
    target = tmp_path / "payload.bin"
    payload = b"0123456789"
    target.write_bytes(payload)

    info = target.stat()

    assert info.st_size == len(payload) == 10
    assert info.st_mtime > 0
    assert info.st_mtime == os.stat(target).st_mtime
    assert stat.S_IFMT(info.st_mode) == stat.S_IFREG


def test_path_unlink_removes_file_and_raises_on_second_call(tmp_path):
    """unlink 删掉真实文件,文件随即不存在;对同一路径再次 unlink 抛 FileNotFoundError。"""
    target = tmp_path / "doomed.txt"
    target.write_bytes(b"bye")
    assert target.exists()

    target.unlink()

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(FileNotFoundError, match="No such file or directory"):
        target.unlink()


def test_path_mkdir_parents_and_exist_ok_combinations(tmp_path):
    """mkdir(parents=True) 一次建出多层目录,exist_ok=True 允许重复创建,否则抛 FileExistsError。"""
    nested = tmp_path / "p" / "q" / "r"
    nested.mkdir(parents=True)

    assert nested.is_dir()
    assert (tmp_path / "p" / "q").is_dir()
    assert (tmp_path / "p").is_dir()

    nested.mkdir(parents=True, exist_ok=True)
    assert nested.is_dir()

    with pytest.raises(FileExistsError, match="File exists"):
        nested.mkdir()


def test_path_rename_moves_and_replace_overwrites_bytes(tmp_path):
    """rename 把文件搬到新名字且字节不变,replace 覆盖已存在目标后目标内容为源文件内容。"""
    source = tmp_path / "source.txt"
    source.write_bytes(b"source-bytes")
    renamed = source.rename(tmp_path / "renamed.txt")

    assert renamed.read_bytes() == b"source-bytes"
    assert renamed.name == "renamed.txt"
    assert not source.exists()

    incoming = tmp_path / "incoming.txt"
    incoming.write_bytes(b"incoming-bytes")
    replaced = incoming.replace(renamed)

    assert replaced == renamed
    assert renamed.read_bytes() == b"incoming-bytes"
    assert not incoming.exists()


def test_path_read_text_and_write_text_roundtrip_utf8(tmp_path):
    """write_text 以 UTF-8 落盘,read_text 读回同一字符串,字节内容等于字符串的 UTF-8 编码。"""
    target = tmp_path / "note.txt"
    text = "量化引擎 ForgeMind\n第二行:αβγ\n"

    target.write_text(text, encoding="utf-8")

    assert target.read_text(encoding="utf-8") == text
    assert target.read_text(encoding="utf-8").splitlines() == [
        "量化引擎 ForgeMind",
        "第二行:αβγ",
    ]
    assert target.read_bytes() == text.encode("utf-8")


def test_path_write_bytes_and_read_bytes_preserve_exact_bytes(tmp_path):
    """write_bytes 写入含 NUL 与高位字节的负载,read_bytes 逐字节取回同样的内容。"""
    target = tmp_path / "blob.bin"
    payload = bytes([0, 1, 2, 127, 128, 255, 0])

    target.write_bytes(payload)

    assert target.read_bytes() == payload
    assert target.read_bytes() == bytes([0, 1, 2, 127, 128, 255, 0])
    assert target.stat().st_size == len(payload) == 7
