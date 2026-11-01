# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 logging 进阶 (Formatter 真格式 / Filter 真匹配) + 真 stat 真 mode 解析 + 真 ntpath / posixpath 真平台特定 + 真 fileinput 进阶 (inplace + backup) + 真 tokenize 进阶 (NL/INDENT 真 token type)。
全 stdlib, 零模拟。
"""
import logging
import stat
import ntpath
import posixpath
import fileinput
import os
import pathlib
import tempfile
import io
import tokenize
import pytest


# ======================== logging 进阶 ========================
def test_logging_formatter_custom():
    """真 Formatter 真格式"""
    logger = logging.getLogger("test_formatter")
    logger.setLevel(logging.DEBUG)
    # 捕获
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    try:
        logger.warning("warning msg")
        logger.error("error msg")
        output = buf.getvalue()
        assert "[WARNING] test_formatter: warning msg" in output
        assert "[ERROR] test_formatter: error msg" in output
    finally:
        logger.removeHandler(handler)


def test_logging_filter():
    """真 Filter 真匹配"""
    class OnlyError(logging.Filter):
        def filter(self, record):
            return record.levelno >= logging.ERROR

    logger = logging.getLogger("test_filter")
    logger.setLevel(logging.DEBUG)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.addFilter(OnlyError())
    logger.addHandler(handler)
    try:
        logger.info("info")  # 应 filter
        logger.error("error")  # 应 pass
        output = buf.getvalue()
        assert "info" not in output
        assert "error" in output
    finally:
        logger.removeHandler(handler)


def test_logging_LogRecord():
    """真 LogRecord 真属性"""
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="/test.py", lineno=42,
        msg="hello %s", args=("world",), exc_info=None
    )
    assert record.name == "test"
    assert record.levelno == logging.INFO
    assert record.getMessage() == "hello world"
    assert record.pathname == "/test.py"
    assert record.lineno == 42


# ======================== stat ========================
def test_stat_mode_bits():
    """真 stat mode bits"""
    # 文件 0o755
    mode = 0o755
    assert stat.S_IMODE(mode) == mode
    # 0o100644 = regular file
    assert stat.S_ISREG(0o100644)
    # 0o040755 = dir
    assert stat.S_ISDIR(0o040755)
    # 0o120000 = symlink
    assert stat.S_ISLNK(0o120000)


def test_stat_S_IS_methods():
    """真 S_IS* 方法"""
    # 文件存在 → S_ISREG
    path = __file__
    mode = os.stat(path).st_mode
    assert stat.S_ISREG(mode)
    assert not stat.S_ISDIR(mode)


def test_stat_filemode():
    """真 stat.filemode 真表示"""
    s = stat.filemode(0o100644)  # -rw-r--r--
    assert s.startswith("-")
    assert "r" in s
    assert "w" in s


# ======================== ntpath / posixpath ========================
def test_posixpath_join():
    """真 posixpath 真 join"""
    assert posixpath.join("a", "b", "c") == "a/b/c"
    assert posixpath.join("/a", "b") == "/a/b"


def test_posixpath_basename_dirname():
    """真 posixpath 真 basename / dirname"""
    assert posixpath.basename("/a/b/c.txt") == "c.txt"
    assert posixpath.dirname("/a/b/c.txt") == "/a/b"


def test_posixpath_splitext():
    """真 posixpath 真 splitext"""
    assert posixpath.splitext("file.tar.gz") == ("file.tar", ".gz")
    assert posixpath.splitext("file") == ("file", "")


def test_ntpath_sep():
    """真 ntpath 真 sep"""
    assert ntpath.sep == "\\"
    assert ntpath.altsep == "/"


# ======================== fileinput 进阶 ========================
def test_fileinput_inplace_with_backup():
    """真 fileinput 真 inplace + backup 真留"""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write("line1\nline2\nline3\n")
    try:
        # 加 prefix 到每行, 留 .bak
        for line in fileinput.input(path, inplace=True, backup=".bak"):
            print("prefix_" + line, end="")
        # 验原文件已改
        content = pathlib.Path(path).read_text()
        assert "prefix_line1" in content
        # 验 backup 存在
        backup_path = path + ".bak"
        assert os.path.isfile(backup_path)
        backup_content = pathlib.Path(backup_path).read_text()
        assert "line1" in backup_content
        # cleanup backup
        os.unlink(backup_path)
    finally:
        os.unlink(path)


def test_fileinput_glob():
    """真 fileinput 真 glob 模式"""
    with tempfile.TemporaryDirectory() as d:
        # 创建多个文件
        for i in range(3):
            with open(os.path.join(d, f"file{i}.txt"), "w") as f:
                f.write(f"content{i}\n")
        # fileinput.FileInput 真 glob
        import glob
        paths = glob.glob(os.path.join(d, "*.txt"))
        assert len(paths) == 3
        # fileinput 真用 paths
        lines = []
        for line in fileinput.input(paths):
            lines.append(line.rstrip())
        assert len(lines) == 3


# ======================== tokenize 进阶 ========================
def test_tokenize_NL_COMMENT():
    """真 tokenize 真 NL / COMMENT token"""
    code = "# comment\nx = 1\n"
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    types = [t.type for t in tokens]
    # 含 COMMENT
    assert tokenize.COMMENT in types
    # 含 NL
    assert tokenize.NL in types or tokenize.NEWLINE in types
    # COMMENT 的 string
    comments = [t.string for t in tokens if t.type == tokenize.COMMENT]
    assert "# comment" in comments


def test_tokenize_OP_precise():
    """真 tokenize 真 OP 真精确"""
    code = "x = 1 + 2 * 3"
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    ops = [t.string for t in tokens if t.type == tokenize.OP]
    # 4 个 OP: = + * (x = 1 是 NAME = NUMBER)
    assert "=" in ops
    assert "+" in ops
    assert "*" in ops
