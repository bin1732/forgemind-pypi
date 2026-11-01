# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""os 模块真实行为测试:进程信息、环境变量、路径运算与目录遍历。

覆盖模块:os、os.path(底层走 posixpath)。
真实测试项(17 项,全部落在真实文件系统与真实 /proc 上):

  1. os.getpid 与 /proc/self 指向同一个内核进程
  2. os.getppid 与 /proc/self/status 的 PPid 字段一致
  3. os.cpu_count 不小于 os.sched_getaffinity 给出的可用 CPU 数
  4. os.environ 的写入、读取与删除形成闭环
  5. os.environ 读取不存在的键抛 KeyError
  6. os.environ 里的 PATH 是含真实分隔符的非空字符串
  7. os.path.exists / isfile 对真实文件与不存在的路径给出确定布尔值
  8. os.path.join 拼接出与 pathlib 一致的真实路径
  9. os.path.split 拆出的目录与文件名能重新拼回原路径
 10. os.path.splitext 按最后一个点分离扩展名
 11. os.path.basename / dirname 对真实文件给出真实名字
 12. os.path.getsize 等于真实写入的字节数
 13. os.stat 报告真实的文件大小、类型与 inode
 14. os.scandir 遍历真实目录得到完整的条目集合
 15. os.scandir 条目的 stat 与 os.stat 指向同一份元数据
 16. os.listdir 与 os.scandir 列出同一批真实条目
 17. os.fspath 接受 str、bytes 与 PathLike,对非法类型抛 TypeError
"""

import os
import stat
import sys
from pathlib import Path

import pytest

IS_LINUX = sys.platform.startswith("linux")


# ======================== 进程信息 ========================
@pytest.mark.skipif(not IS_LINUX, reason="需要 Linux 的 /proc 伪文件系统")
def test_os_getpid_matches_proc_self():
    """os.getpid() 返回当前进程号,且与 /proc/self 的真实指向一致。

    /proc/self 是指向本进程 /proc/<pid> 目录的符号链接,解析后的路径
    必须与 os.getpid() 拼出的目录名完全相同。
    """
    pid = os.getpid()
    assert isinstance(pid, int)
    assert pid > 0
    assert os.path.realpath("/proc/self") == f"/proc/{pid}"
    assert os.path.isdir(f"/proc/{pid}")
    assert os.path.exists(f"/proc/{pid}/stat")


@pytest.mark.skipif(not IS_LINUX, reason="需要 Linux 的 /proc 伪文件系统")
def test_os_getppid_matches_proc_status_ppid():
    """os.getppid() 与 /proc/self/status 中记录的 PPid 字段完全相同。

    内核给出的父进程号与 Python 层的 os.getppid() 必须一致,
    说明拿到的是真实父子关系,而不是接口自说自话。
    """
    ppid = os.getppid()
    assert isinstance(ppid, int)
    assert ppid > 0
    status = Path("/proc/self/status").read_text(encoding="utf-8")
    recorded = None
    for line in status.splitlines():
        if line.startswith("PPid:"):
            recorded = int(line.split()[1])
            break
    assert recorded is not None
    assert recorded == ppid
    assert os.path.isdir(f"/proc/{ppid}")


@pytest.mark.skipif(
    not hasattr(os, "sched_getaffinity"),
    reason="需要 Linux 的 os.sched_getaffinity",
)
def test_os_cpu_count_covers_sched_affinity():
    """os.cpu_count() 不小于 os.sched_getaffinity(0) 返回的可用 CPU 数。

    亲和集合里的每个 CPU 编号都必须落在 os.cpu_count() 给出的总数范围内,
    亲和集合本身至少包含 1 个 CPU。
    """
    total = os.cpu_count()
    assert total is not None
    assert total >= 1
    affinity = os.sched_getaffinity(0)
    assert len(affinity) >= 1
    assert total >= len(affinity)
    assert all(0 <= cpu < total for cpu in affinity)


# ======================== 环境变量 ========================
def test_os_environ_set_get_delete_roundtrip():
    """os.environ 写入后能读回同样的字符串,删除后键确实消失。

    环境变量是 os._Environ 映射,写入会同步到进程环境,读回值必须与
    写入值逐字符相同。
    """
    key = "FORGEMIND_OS_SYS_TIME_BATCH_A"
    assert key not in os.environ
    os.environ[key] = "value-A"
    assert os.environ[key] == "value-A"
    assert os.environ.get(key) == "value-A"
    del os.environ[key]
    assert key not in os.environ
    assert os.environ.get(key) is None


def test_os_environ_missing_key_raises_keyerror():
    """读取一个确实不存在的环境变量键会抛 KeyError。

    os.environ["<不存在的键>"] 必须抛 KeyError 而不是静默返回 None,
    os.environ.get 对同一个键返回 None,两种取值方式行为不同。
    """
    missing = "FORGEMIND_ENV_KEY_THAT_DOES_NOT_EXIST_9C1F"
    assert missing not in os.environ
    with pytest.raises(KeyError):
        os.environ[missing]
    assert os.environ.get(missing) is None
    assert os.environ.get(missing, "fallback") == "fallback"


def test_os_environ_contains_path_with_real_value():
    """os.environ 中的 PATH 是一条含真实路径分隔符的非空字符串。

    以 os.pathsep 连接出至少一个目录项,且其中有绝对路径,
    说明进程拿到了真实的环境配置。
    """
    assert "PATH" in os.environ
    raw = os.environ["PATH"]
    assert isinstance(raw, str)
    assert raw != ""
    assert os.pathsep in raw
    segments = [seg for seg in raw.split(os.pathsep) if seg]
    assert len(segments) >= 1
    assert any(os.path.isabs(seg) for seg in segments)


# ======================== 路径运算 ========================
def test_os_path_exists_on_real_file_and_missing_path(tmp_path):
    """os.path.exists / isfile / isdir 对真实文件给出确定的布尔结果。

    测试目录下真实写入的文件 exists 与 isfile 均为 True、isdir 为 False;
    一个不存在的路径 exists 为 False。
    """
    real = tmp_path / "payload.bin"
    real.write_bytes(b"forgemind")
    missing = tmp_path / "not-created.bin"

    assert os.path.exists(str(real)) is True
    assert os.path.isfile(str(real)) is True
    assert os.path.isdir(str(real)) is False
    assert os.path.exists(str(missing)) is False
    assert os.path.isfile(str(missing)) is False
    assert os.path.isdir(str(tmp_path)) is True


def test_os_path_join_builds_real_path(tmp_path):
    """os.path.join 的结果与 pathlib 的路径拼接结果完全一致。

    多个片段按顺序拼接,遇到绝对路径片段时按 POSIX 规则丢弃前缀。
    """
    joined = os.path.join(str(tmp_path), "sub", "leaf.txt")
    assert joined == str(tmp_path / "sub" / "leaf.txt")
    assert os.path.dirname(joined) == str(tmp_path / "sub")

    if os.name == "posix":
        rooted = os.path.join(str(tmp_path), os.sep + "absolute")
        assert rooted == os.sep + "absolute"


def test_os_path_split_rejoins_to_original(tmp_path):
    """os.path.split 拆出的 (目录, 文件名) 能重新拼回原路径。

    对真实文件路径,目录部分等于父目录,文件名部分等于文件名。
    """
    target = tmp_path / "report.txt"
    target.write_text("x", encoding="utf-8")
    raw = str(target)

    directory, base = os.path.split(raw)
    assert directory == str(tmp_path)
    assert base == "report.txt"
    assert os.path.join(directory, base) == raw
    assert os.path.split(raw)[0] == os.path.dirname(raw)


def test_os_path_splitext_separates_suffix():
    """os.path.splitext 只按最后一个点分离扩展名。

    "report.tar.gz" 拆成 ("report.tar", ".gz");无扩展名的文件扩展名为空串;
    以点开头的隐藏文件不产生扩展名。
    """
    assert os.path.splitext("report.tar.gz") == ("report.tar", ".gz")
    assert os.path.splitext("noext") == ("noext", "")
    assert os.path.splitext(".hidden") == (".hidden", "")
    assert os.path.splitext("archive.") == ("archive", ".")


def test_os_path_basename_and_dirname_on_real_file(tmp_path):
    """os.path.basename / dirname 对真实文件给出真实的目录与文件名。

    basename 只取最后一段,dirname 给出包含全部父目录的绝对路径。
    """
    target = tmp_path / "data" / "kline.csv"
    target.parent.mkdir()
    target.write_text("1,2,3\n", encoding="utf-8")
    raw = str(target)

    assert os.path.basename(raw) == "kline.csv"
    assert os.path.dirname(raw) == str(tmp_path / "data")
    assert os.path.dirname(os.path.dirname(raw)) == str(tmp_path)


def test_os_path_getsize_matches_written_bytes(tmp_path):
    """os.path.getsize 等于真实写入的字节数。

    写入 1234 字节后 getsize 必须精确等于 1234,改写为 7 字节后同步变成 7。
    """
    target = tmp_path / "size.bin"
    target.write_bytes(b"x" * 1234)
    assert os.path.getsize(str(target)) == 1234

    target.write_bytes(b"y" * 7)
    assert os.path.getsize(str(target)) == 7
    assert os.path.getsize(str(target)) == len(target.read_bytes())


def test_os_path_stat_reports_real_size_and_mode(tmp_path):
    """os.stat 返回的 st_size / st_mode / st_ino 与真实文件一致。

    st_size 等于写入字节数,st_mode 判定为普通文件,st_ino 是可复用的
    真实 inode 号,两次 stat 得到同一个 inode。
    """
    target = tmp_path / "stat-target.txt"
    payload = b"forgemind-os-stat"
    target.write_bytes(payload)

    st = os.stat(str(target))
    assert st.st_size == len(payload)
    assert stat.S_ISREG(st.st_mode) is True
    assert stat.S_ISDIR(st.st_mode) is False
    assert st.st_nlink == 1
    assert st.st_ino == os.stat(str(target)).st_ino
    assert st.st_ino > 0
    assert st.st_dev > 0


# ======================== 目录遍历 ========================
def test_os_scandir_lists_real_directory_entries(tmp_path):
    """os.scandir 遍历真实目录,得到与磁盘上一致的完整条目集合。

    三个普通文件加一个子目录,条目名集合与实际写入的名字完全相同,
    并且每个条目的 is_file / is_dir 判定正确。
    """
    for name in ("a.txt", "b.txt", "c.bin"):
        (tmp_path / name).write_text("data", encoding="utf-8")
    (tmp_path / "nested").mkdir()

    with os.scandir(str(tmp_path)) as entries:
        found = {entry.name: entry for entry in entries}

    assert set(found) == {"a.txt", "b.txt", "c.bin", "nested"}
    assert found["a.txt"].is_file() is True
    assert found["a.txt"].is_dir() is False
    assert found["nested"].is_dir() is True
    assert found["nested"].is_file() is False
    assert all(entry.path.endswith(entry.name) for entry in found.values())


def test_os_scandir_entry_stat_matches_path_stat(tmp_path):
    """scandir 条目自带的 stat 与按路径调用 os.stat 得到同一份元数据。

    两者的 st_size、st_ino、st_mtime 必须完全相同,证明条目没有缓存偏差。
    """
    target = tmp_path / "scandir-stat.bin"
    target.write_bytes(b"z" * 4096)

    with os.scandir(str(tmp_path)) as entries:
        entry = next(item for item in entries if item.name == "scandir-stat.bin")
        entry_stat = entry.stat()

    path_stat = os.stat(entry.path)
    assert entry_stat.st_size == 4096
    assert entry_stat.st_size == path_stat.st_size
    assert entry_stat.st_ino == path_stat.st_ino
    assert entry_stat.st_mtime == path_stat.st_mtime


def test_os_listdir_matches_scandir_names(tmp_path):
    """os.listdir 与 os.scandir 列出同一批真实条目。

    两者按名称排序后必须完全相等,说明两个 API 读取的是同一份目录内容。
    """
    for name in ("x.txt", "y.txt", "z.txt"):
        (tmp_path / name).write_text("1", encoding="utf-8")

    listed = sorted(os.listdir(str(tmp_path)))
    with os.scandir(str(tmp_path)) as entries:
        scanned = sorted(entry.name for entry in entries)

    assert listed == ["x.txt", "y.txt", "z.txt"]
    assert listed == scanned
    assert set(listed) == set(scanned)


def test_os_fspath_accepts_str_and_pathlike(tmp_path):
    """os.fspath 对 str、bytes、PathLike 都返回等价的原始路径。

    str 与 Path 被转换成同一条字符串路径,bytes 保持 bytes 类型,
    整数这种不支持路径协议的类型会抛 TypeError。
    """
    target = tmp_path / "fspath.txt"
    target.write_text("ok", encoding="utf-8")

    assert os.fspath(str(target)) == str(target)
    assert os.fspath(target) == str(target)
    assert os.fspath(b"raw/bytes/path") == b"raw/bytes/path"
    with pytest.raises(TypeError):
        os.fspath(123)
    with pytest.raises(TypeError):
        os.fspath(None)
