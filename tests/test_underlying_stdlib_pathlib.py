# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 stdlib pathlib — Path 真操作 + glob + rglob + resolve + read/write + stat。
"""
import os
import pathlib
import platform
import tempfile
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

import pytest


def test_path_constructor_and_parts():
    """Path 真分 parts + name + suffix + stem"""
    p = Path("/usr/local/bin/python3")
    assert p.parts == ("/", "usr", "local", "bin", "python3")
    assert p.name == "python3"
    assert p.suffix == ""
    assert p.stem == "python3"
    p2 = Path("/tmp/test.txt")
    assert p2.suffix == ".txt"
    assert p2.stem == "test"


def test_path_joinpath_real():
    """Path 真 / 操作符 join"""
    p = Path("/usr") / "local" / "bin"
    assert str(p) == "/usr/local/bin"
    assert isinstance(p, Path)


def test_path_mkdir_rmdir_real(tmp_path):
    """Path 真 mkdir / rmdir / exists"""
    d = tmp_path / "new_dir"
    assert not d.exists()
    d.mkdir()
    assert d.exists()
    assert d.is_dir()
    d.rmdir()
    assert not d.exists()


def test_path_touch_unlink_real(tmp_path):
    """Path 真 touch / unlink"""
    f = tmp_path / "file.txt"
    assert not f.exists()
    f.touch()
    assert f.exists()
    assert f.stat().st_size == 0
    f.unlink()
    assert not f.exists()


def test_path_read_write_text_real(tmp_path):
    """Path 真 read_text / write_text 100% 一致"""
    f = tmp_path / "data.txt"
    text = "Hello, World!\n" * 100
    f.write_text(text)
    assert f.read_text() == text
    # 验 1MB binary
    f2 = tmp_path / "data.bin"
    data = os.urandom(1024 * 1024)
    f2.write_bytes(data)
    assert f2.read_bytes() == data


def test_path_glob_rglob_real(tmp_path):
    """Path 真 glob / rglob 真匹配"""
    # 创 5 个 .py + 3 个 .txt
    for i in range(5):
        (tmp_path / f"file_{i}.py").touch()
    for i in range(3):
        (tmp_path / f"file_{i}.txt").touch()
    # 子目录
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.py").touch()

    py_files = list(tmp_path.glob("*.py"))
    assert len(py_files) == 5, f"glob *.py 应 5, 实际 {len(py_files)}"
    txt_files = list(tmp_path.glob("*.txt"))
    assert len(txt_files) == 3
    # rglob 真递归
    all_py = list(tmp_path.rglob("*.py"))
    assert len(all_py) == 6, f"rglob *.py 应 6 (含 sub/nested.py), 实际 {len(all_py)}"


def test_path_with_suffix_with_stem_real():
    """Path 真 with_suffix / with_stem / with_name"""
    p = Path("/tmp/test.py")
    assert str(p.with_suffix(".txt")) == "/tmp/test.txt"
    assert str(p.with_stem("renamed")) == "/tmp/renamed.py"
    assert str(p.with_name("other.py")) == "/tmp/other.py"


def test_path_resolve_real(tmp_path):
    """Path 真 resolve 真解析 .. 和 . 和 symlink"""
    d = tmp_path / "real_dir"
    d.mkdir()
    link = tmp_path / "link_to_dir"
    if hasattr(os, "symlink"):
        try:
            os.symlink(str(d), str(link))
        except (OSError, NotImplementedError):
            pytest.skip("沙箱不支持 symlink")

    resolved = link.resolve()
    assert resolved.is_dir()
    # 解析后应指向 real_dir
    assert resolved == d.resolve(), f"resolve 应指向 {d}, 实际 {resolved}"


def test_path_is_file_is_dir_real(tmp_path):
    """Path 真 is_file / is_dir 区分"""
    f = tmp_path / "file.txt"
    f.touch()
    d = tmp_path / "dir"
    d.mkdir()

    assert f.is_file()
    assert not f.is_dir()
    assert d.is_dir()
    assert not d.is_file()


def test_path_iterdir_real(tmp_path):
    """Path 真 iterdir 列举目录内容"""
    files = [f"f_{i}.txt" for i in range(5)]
    for name in files:
        (tmp_path / name).touch()

    listed = sorted(p.name for p in tmp_path.iterdir())
    assert listed == files


def test_path_relative_to_real():
    """Path 真 relative_to 算相对路径"""
    p = Path("/usr/local/bin/python3")
    rel = p.relative_to("/usr/local")
    assert str(rel) == "bin/python3"


def test_path_exists_is_absolute_real():
    """Path 真 exists / is_absolute"""
    p = Path("/usr/local/bin")
    assert p.is_absolute()
    # 不存在
    p2 = Path("/nonexistent/never/12345")
    assert not p2.exists()


def test_path_home_real():
    """Path.home() 真返 user home"""
    h = Path.home()
    assert h.is_absolute()
    # 沙箱 HOME 应设
    assert str(h) == os.environ.get("HOME", str(h))


def test_path_pure_path_real():
    """PurePath 真纯字符串操作 (不真访问 fs)"""
    p = PurePosixPath("/usr/local/bin")
    assert str(p) == "/usr/local/bin"
    assert p.parts == ("/", "usr", "local", "bin")


def test_path_stat_real(tmp_path):
    """Path 真 stat 返真 stat 结果"""
    f = tmp_path / "x.txt"
    f.write_text("abc")  # 3 字节
    st = f.stat()
    assert st.st_size == 3
    assert st.st_mode  # 应有 mode
