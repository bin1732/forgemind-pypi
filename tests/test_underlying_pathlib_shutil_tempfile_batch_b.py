# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""pathlib 进阶语义与 shutil 复制家族的底层真实行为验证。

覆盖模块:pathlib(标准库)、shutil(标准库)

真测试项(18 个):
  1. absolute() 与 Path.cwd() 返回磁盘上的绝对路径
  2. relative_to / is_relative_to 在真实目录树上判定归属
  3. match() 用 glob 模式匹配真实文件名
  4. as_posix() 与 anchor 暴露路径结构信息
  5. expanduser() 把 ~ 展开成真实 home 目录
  6. symlink_to / readlink 建立并读取真实符号链接
  7. hardlink_to 让两个路径共享同一 inode 与内容
  8. touch() 建文件并把 mtime 推到当前时刻
  9. samefile() 判定两个路径是否指向同一文件
 10. Path.walk() 自顶向下遍历目录树(3.12+ 能力,低版本按 hasattr 跳过)
 11. relative_to(walk_up=True) 生成带 .. 的上级路径(3.12+ 能力)
 12. Path.full_match() 要求模式覆盖整条路径(3.13+ 能力)
 13. shutil.copy 复制字节与权限位但不保留 mtime
 14. shutil.copy2 复制字节、权限位与 mtime
 15. shutil.copyfile 只复制字节,不复制权限位与时间戳
 16. shutil.copystat 复制权限位与时间戳
 17. shutil.copymode 只复制权限位,时间戳保持不变
 18. shutil.copymode / copystat 的差异在真实文件上可分辨
"""

import inspect
import os
import stat
from pathlib import Path

import pytest
import shutil

# 3.12 起 shutil.rmtree 增加 onexc 关键字参数(错误回调收到异常实例而非 exc_info 三元组)。
_HAS_RMTREE_ONEXC = hasattr(shutil, "rmtree") and "onexc" in inspect.signature(shutil.rmtree).parameters


def test_path_absolute_and_cwd_return_absolute_real_paths(tmp_path):
    """absolute() 把相对路径补成基于当前工作目录的绝对路径,cwd() 就是进程真实工作目录。"""
    relative = Path("relative-name.txt")

    absolute = relative.absolute()

    assert absolute.is_absolute()
    assert absolute == Path.cwd() / "relative-name.txt"
    assert Path.cwd() == Path(os.getcwd())
    assert Path.cwd().is_dir()
    assert (tmp_path / "child").absolute() == tmp_path / "child"


def test_path_relative_to_and_is_relative_to_on_real_tree(tmp_path):
    """relative_to 取出相对片段,is_relative_to 按真实目录层级判定路径归属。"""
    nested = tmp_path / "pkg" / "sub"
    nested.mkdir(parents=True)
    target = nested / "module.py"

    relative = target.relative_to(tmp_path)

    assert str(relative) == os.path.join("pkg", "sub", "module.py")
    assert relative.name == "module.py"
    assert target.is_relative_to(tmp_path) is True
    assert target.is_relative_to(tmp_path / "pkg") is True
    assert target.is_relative_to(tmp_path / "other") is False


def test_path_match_matches_patterns_against_real_names(tmp_path):
    """match() 从右侧逐段匹配 glob 模式,命中与不命中都按真实文件名判定。"""
    report = tmp_path / "daily-report.csv"

    assert report.match("*.csv") is True
    assert report.match("*.json") is False
    assert report.match("daily-*.csv") is True
    assert report.match("daily-report.csv") is True
    assert report.match("missing-report.csv") is False


def test_path_as_posix_and_anchor_expose_path_structure(tmp_path):
    """as_posix() 统一输出正斜杠形式,anchor 给出根锚点,parts 保留各级目录。"""
    target = tmp_path / "level1" / "level2" / "file.bin"

    assert target.as_posix() == str(target).replace(os.sep, "/")
    assert target.anchor == "/"
    assert target.parts[0] == "/"
    assert target.parts[-2:] == ("level2", "file.bin")
    assert target.root == "/"


def test_path_expanduser_expands_home_prefix():
    """expanduser() 把 ~ 展开成真实的 home 目录,与 Path.home() 结果一致。"""
    home = Path.home()

    assert home.is_dir()
    assert Path("~").expanduser() == home
    assert Path("~/sub").expanduser() == home / "sub"
    assert Path("~").expanduser().is_absolute()


def test_path_symlink_to_and_readlink_point_to_target(tmp_path):
    """symlink_to 建立真实符号链接,readlink 读回目标路径,经链接读到的字节与源文件一致。"""
    source = tmp_path / "target.txt"
    source.write_bytes(b"payload-bytes")
    link = tmp_path / "link.txt"
    link.symlink_to(source)

    assert link.is_symlink() is True
    assert os.readlink(link) == str(source)
    assert link.readlink() == source
    assert link.read_bytes() == b"payload-bytes"
    assert link.resolve() == source.resolve()


def test_path_hardlink_to_shares_inode_and_content(tmp_path):
    """hardlink_to 让两条路径指向同一 inode,内容与 stat 全部一致。"""
    source = tmp_path / "original.bin"
    source.write_bytes(b"shared-content")
    hard = tmp_path / "hard.bin"
    hard.hardlink_to(source)

    assert hard.stat().st_ino == source.stat().st_ino
    assert hard.read_bytes() == b"shared-content"
    assert hard.samefile(source) is True
    assert hard.stat().st_nlink == 2


def test_path_touch_creates_file_and_updates_mtime(tmp_path):
    """touch() 新建空文件,再次调用把 mtime 推到比设定值更晚的时刻。"""
    target = tmp_path / "touched.txt"
    target.touch()
    assert target.exists()
    assert target.stat().st_size == 0

    os.utime(target, (1_000_000_000, 1_000_000_000))
    stale_mtime = target.stat().st_mtime

    target.touch()

    assert target.stat().st_mtime > stale_mtime
    assert target.stat().st_size == 0


def test_path_samefile_identifies_same_underlying_file(tmp_path):
    """samefile() 对同一文件的两个路径返回真,对不同文件返回假。"""
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    assert first.samefile(first) is True
    assert first.samefile(second) is False
    assert first.samefile(str(first)) is True


@pytest.mark.skipif(not hasattr(Path, "walk"), reason="Path.walk 需要 Python 3.12+")
def test_path_walk_yields_directory_tree_top_down(tmp_path):
    """Path.walk() 逐个产出 (目录, 子目录名, 文件名) 三元组,目录与文件名都对应磁盘实况。"""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "module.py").write_bytes(b"code")
    (tmp_path / "top.txt").write_bytes(b"top")

    walked = {}
    for directory, dirnames, filenames in tmp_path.walk():
        walked[directory] = (sorted(dirnames), sorted(filenames))

    assert walked[tmp_path] == (["pkg"], ["top.txt"])
    assert walked[tmp_path / "pkg"] == ([], ["module.py"])
    assert set(walked) == {tmp_path, tmp_path / "pkg"}


@pytest.mark.skipif(
    not (hasattr(Path, "relative_to") and "walk_up" in inspect.signature(Path.relative_to).parameters),
    reason="relative_to(walk_up=True) 需要 Python 3.12+",
)
def test_path_relative_to_walk_up_builds_parent_segments():
    """relative_to(walk_up=True) 在无共同子路径时生成带 .. 的上级相对路径。"""
    relative = Path("/etc/passwd").relative_to("/usr", walk_up=True)

    assert str(relative) == os.path.join("..", "etc", "passwd")
    assert relative.parts[0] == ".."
    assert relative.name == "passwd"


@pytest.mark.skipif(not hasattr(Path, "full_match"), reason="Path.full_match 需要 Python 3.13+")
def test_path_full_match_requires_pattern_to_cover_whole_path():
    """full_match() 要求模式覆盖整条路径,** 模式可跨目录层级,单段模式不能跨层级。"""
    target = Path("pkg/sub/module.py")

    assert target.full_match("pkg/sub/module.py") is True
    assert target.full_match("pkg/*.py") is True
    assert target.full_match("**/*.py") is True
    assert target.full_match("*.py") is False
    assert target.full_match("pkg/sub/*.json") is False


def test_shutil_copy_preserves_bytes_and_permission_but_not_mtime(tmp_path):
    """shutil.copy 复制文件字节与权限位,mtime 换成复制发生的时间而非源文件时间。"""
    source = tmp_path / "source.bin"
    source.write_bytes(b"copied-bytes")
    os.chmod(source, 0o640)
    os.utime(source, (1_000_000_000, 1_000_000_000))
    target = tmp_path / "target.bin"

    shutil.copy(source, target)

    assert target.read_bytes() == b"copied-bytes"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert target.stat().st_mtime != 1_000_000_000


def test_shutil_copy2_preserves_bytes_permission_and_mtime(tmp_path):
    """shutil.copy2 连同权限位与 mtime 一起复制,目标字节与源文件完全一致。"""
    source = tmp_path / "source2.bin"
    source.write_bytes(b"full-metadata")
    os.chmod(source, 0o600)
    os.utime(source, (1_000_000_000, 1_000_000_000))
    target = tmp_path / "target2.bin"

    shutil.copy2(source, target)

    assert target.read_bytes() == b"full-metadata"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.stat().st_mtime == 1_000_000_000


def test_shutil_copyfile_copies_bytes_without_metadata(tmp_path):
    """shutil.copyfile 只搬字节,目标权限位是新建文件的默认值,时间戳也未被复制。"""
    source = tmp_path / "source3.bin"
    source.write_bytes(b"bytes-only")
    os.chmod(source, 0o600)
    os.utime(source, (1_000_000_000, 1_000_000_000))
    reference = tmp_path / "reference.bin"
    reference.write_bytes(b"")
    target = tmp_path / "target3.bin"

    shutil.copyfile(source, target)

    assert target.read_bytes() == b"bytes-only"
    assert stat.S_IMODE(target.stat().st_mode) == stat.S_IMODE(reference.stat().st_mode)
    assert target.stat().st_mtime != 1_000_000_000


def test_shutil_copystat_copies_permission_and_timestamps(tmp_path):
    """shutil.copystat 把权限位、atime 与 mtime 一并搬到目标文件上。"""
    source = tmp_path / "meta-source.bin"
    source.write_bytes(b"meta")
    os.chmod(source, 0o640)
    os.utime(source, (1_000_000_000, 1_600_000_000))
    target = tmp_path / "meta-target.bin"
    target.write_bytes(b"meta-target")

    shutil.copystat(source, target)

    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert target.stat().st_mtime == 1_600_000_000
    assert target.read_bytes() == b"meta-target"


def test_shutil_copymode_copies_permission_bits_only(tmp_path):
    """shutil.copymode 只搬权限位,目标的 mtime 保持自己的取值不变。"""
    source = tmp_path / "mode-source.bin"
    source.write_bytes(b"mode")
    os.chmod(source, 0o750)
    os.utime(source, (1_000_000_000, 1_000_000_000))
    target = tmp_path / "mode-target.bin"
    target.write_bytes(b"mode-target")
    original_mtime = target.stat().st_mtime

    shutil.copymode(source, target)

    assert stat.S_IMODE(target.stat().st_mode) == 0o750
    assert target.stat().st_mtime == original_mtime
    assert target.read_bytes() == b"mode-target"
