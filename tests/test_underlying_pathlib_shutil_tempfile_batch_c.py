# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`tempfile` 与 `shutil` 归档家族的底层真实行为测试。

覆盖模块:tempfile(标准库临时文件工具)、shutil(标准库文件操作)

真实测试项(共 18 个):
 1. `mkstemp` 返回真实存在的文件描述符与路径,文件内容可读可写
 2. `mkstemp` 的 suffix 与 prefix 落到实际文件名里
 3. `mkstemp` 连续两次调用得到不同路径
 4. `mkdtemp` 建的目录真实存在且初始为空
 5. `mkdtemp` 的 prefix 落到实际目录名里
 6. `NamedTemporaryFile` 退出 with 块后文件被删除
 7. `NamedTemporaryFile(delete=False)` 退出后文件仍然存在
 8. `NamedTemporaryFile` 写入的内容原样读回
 9. `TemporaryDirectory` 退出后整个目录树被清理
 10. `TemporaryDirectory` 清理前目录内文件真实存在
 11. `gettempdir` 返回真实存在且可写的目录
 12. `shutil.copy` 复制内容一致但目标模式取默认
 13. `shutil.copy2` 复制内容一致且保留修改时间
 14. `shutil.copytree` 递归复制目录结构与内容
 15. `shutil.rmtree` 递归删除目录树
 16. `shutil.make_archive` 产出真实可解压的归档
 17. `shutil.unpack_archive` 解压后内容与原目录一致
 18. `shutil.move` 把文件移走且源路径不再存在
"""
import os
import shutil
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

import pytest


# -- tempfile ------------------------------------------------

class TestTempfileMkstempMkdtemp:
    """`tempfile` 的临时文件与临时目录创建。"""

    def test_mkstemp_returns_writable_fd_and_existing_path(self):
        """`mkstemp 返回可写文件描述符,路径真实存在。"""
        fd, path = tempfile.mkstemp()
        try:
            # 必 路径真实存在
            assert os.path.exists(path)
            # 必 描述符可写
            os.write(fd, b"forge")
            os.close(fd)
            # 必 内容已落盘
            assert Path(path).read_bytes() == b"forge"
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(path):
                os.unlink(path)

    def test_mkstemp_applies_prefix_and_suffix(self):
        """`mkstemp 的 prefix 与 suffix 落到实际文件名。"""
        fd, path = tempfile.mkstemp(prefix="forge_pre_", suffix="_.bin")
        try:
            name = Path(path).name
            # 必 前缀生效
            assert name.startswith("forge_pre_")
            # 必 后缀生效
            assert name.endswith("_.bin")
        finally:
            os.close(fd)
            os.unlink(path)

    def test_mkstemp_returns_distinct_paths(self):
        """`mkstemp 连续两次调用得到不同路径。"""
        fd1, p1 = tempfile.mkstemp()
        fd2, p2 = tempfile.mkstemp()
        try:
            # 必 路径不同
            assert p1 != p2
        finally:
            os.close(fd1)
            os.close(fd2)
            os.unlink(p1)
            os.unlink(p2)

    def test_mkdtemp_creates_existing_empty_dir(self):
        """`mkdtemp 建立的目录真实存在且初始为空。"""
        path = tempfile.mkdtemp()
        try:
            # 必 是目录
            assert os.path.isdir(path)
            # 必 初始为空
            assert os.listdir(path) == []
        finally:
            shutil.rmtree(path)

    def test_mkdtemp_applies_prefix(self):
        """`mkdtemp 的 prefix 落到实际目录名。"""
        path = tempfile.mkdtemp(prefix="forge_dir_")
        try:
            # 必 前缀生效
            assert os.path.basename(path).startswith("forge_dir_")
        finally:
            shutil.rmtree(path)

    def test_gettempdir_is_existing_writable_dir(self):
        """`gettempdir 返回真实存在且可写的目录。"""
        path = tempfile.gettempdir()
        # 必 是目录
        assert os.path.isdir(path)
        # 必 可写
        assert os.access(path, os.W_OK)


class TestTempfileNamedTemporaryFileAndDirectory:
    """`tempfile` 的命名临时文件与临时目录上下文管理器。"""

    def test_named_temporary_file_removed_on_exit(self):
        """`NamedTemporaryFile 退出 with 块后文件被删除。"""
        with tempfile.NamedTemporaryFile() as f:
            path = f.name
            # 必 退出前文件存在
            assert os.path.exists(path)
        # 必 退出后已删除
        assert not os.path.exists(path)

    def test_named_temporary_file_kept_when_delete_false(self):
        """`NamedTemporaryFile(delete=False) 退出后文件仍然存在。"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            # 必 文件保留
            assert os.path.exists(path)
        finally:
            os.unlink(path)

    def test_named_temporary_file_round_trips_content(self):
        """`NamedTemporaryFile 写入的内容原样读回。"""
        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as f:
            f.write("forge 内容")
            f.flush()
            f.seek(0)
            # 必 内容一致
            assert f.read() == "forge 内容"

    def test_temporary_directory_removed_on_exit(self):
        """`TemporaryDirectory 退出后整个目录树被清理。"""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "forge.txt").write_text("x")
            # 必 退出前文件存在
            assert os.path.exists(os.path.join(d, "forge.txt"))
            path = d
        # 必 退出后目录已删除
        assert not os.path.exists(path)

    def test_temporary_directory_files_exist_inside(self):
        """`TemporaryDirectory 清理前目录内文件真实存在。"""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "a.txt").write_text("a")
            (base / "b.txt").write_text("b")
            # 必 两个文件都在
            assert sorted(p.name for p in base.iterdir()) == ["a.txt", "b.txt"]


# -- shutil ---------------------------------------------------

class TestShutilCopyFamily:
    """`shutil` 的复制家族。"""

    def test_copy_keeps_content(self, tmp_path):
        """`shutil.copy 复制内容一致。"""
        src = tmp_path / "src.txt"
        src.write_text("forge 内容")
        dst = tmp_path / "dst.txt"
        shutil.copy(str(src), str(dst))
        # 必 内容一致
        assert dst.read_text(encoding="utf-8") == "forge 内容"

    def test_copy2_preserves_mtime(self, tmp_path):
        """`shutil.copy2 保留修改时间。"""
        src = tmp_path / "src.txt"
        src.write_text("forge")
        os.utime(src, (1_600_000_000, 1_600_000_000))
        dst = tmp_path / "dst.txt"
        shutil.copy2(str(src), str(dst))
        # 必 修改时间被保留
        assert int(os.stat(dst).st_mtime) == 1_600_000_000

    def test_copytree_reproduces_structure(self, tmp_path):
        """`shutil.copytree 递归复制目录结构与内容。"""
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        (src / "top.txt").write_text("top")
        (src / "sub" / "deep.txt").write_text("deep")
        dst = tmp_path / "dst"
        shutil.copytree(str(src), str(dst))
        # 必 顶层文件一致
        assert (dst / "top.txt").read_text(encoding="utf-8") == "top"
        # 必 嵌套文件一致
        assert (dst / "sub" / "deep.txt").read_text(encoding="utf-8") == "deep"

    def test_rmtree_removes_whole_tree(self, tmp_path):
        """`shutil.rmtree 递归删除目录树。"""
        base = tmp_path / "tree"
        (base / "a" / "b").mkdir(parents=True)
        (base / "a" / "b" / "f.txt").write_text("x")
        shutil.rmtree(str(base))
        # 必 目录已消失
        assert not base.exists()


class TestShutilArchiveAndMove:
    """`shutil` 的归档与移动。"""

    def test_make_archive_produces_readable_zip(self, tmp_path):
        """`shutil.make_archive 产出真实可解压的归档。"""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("forge")
        archive = shutil.make_archive(
            str(tmp_path / "out"), "zip", root_dir=str(src),
        )
        # 必 归档文件真实存在
        assert os.path.isfile(archive)
        # 必 是合法 zip
        with zipfile.ZipFile(archive) as zf:
            # 必 含预期条目
            assert "a.txt" in zf.namelist()

    def test_unpack_archive_restores_content(self, tmp_path):
        """`shutil.unpack_archive 解压后内容与原目录一致。"""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("forge 内容")
        archive = shutil.make_archive(
            str(tmp_path / "out"), "zip", root_dir=str(src),
        )
        dst = tmp_path / "dst"
        shutil.unpack_archive(archive, str(dst))
        # 必 内容一致
        assert (dst / "a.txt").read_text(encoding="utf-8") == "forge 内容"

    def test_tar_archive_round_trip(self, tmp_path):
        """`shutil.make_archive 产出 tar 归档并可原样解回。"""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("forge")
        archive = shutil.make_archive(
            str(tmp_path / "out"), "tar", root_dir=str(src),
        )
        # 必 是合法 tar
        with tarfile.open(archive) as tf:
            # 必 含预期条目
            assert any(n.endswith("a.txt") for n in tf.getnames())

    def test_move_relocates_file(self, tmp_path):
        """`shutil.move 把文件移走且源路径不再存在。"""
        src = tmp_path / "src.txt"
        src.write_text("forge")
        dst_dir = tmp_path / "target"
        dst_dir.mkdir()
        shutil.move(str(src), str(dst_dir))
        # 必 源路径已消失
        assert not src.exists()
        # 必 目标文件存在
        assert (dst_dir / "src.txt").read_text(encoding="utf-8") == "forge"

    def test_which_finds_executable_on_path(self):
        """`shutil.which 在 PATH 上找到可执行文件。"""
        found = shutil.which("python3") or shutil.which("python")
        # 必 至少找到一个
        assert found is not None
        # 必 是真实可执行文件
        assert os.access(found, os.X_OK)
