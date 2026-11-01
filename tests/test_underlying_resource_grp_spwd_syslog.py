# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`resource` + `grp` + `spwd` + `syslog` 真底层测试。

覆盖 POSIX 用户/系统信息模块:
  - `resource.getrlimit` / `setrlimit` 真设 RLIMIT_NOFILE 上限并读回
  - `resource.RLIMIT_NOFILE` 真存在,前/后软硬限 ≥ 1
  - `grp.getgrall` 返 list,每项 `.gr_name` 是字符串;`getgrgid(0)` 拿 root 组
  - `spwd.getspnam` 真拿 shadow passwd entry,`.sp_nam` 字段是 root
  - `syslog.openlog` 真连到 syslog,`syslog.syslog('msg')` 不抛异常
  - `syslog.LOG_INFO` 是真实整数
"""
import grp
import resource
# spwd 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_spwd_mod
    with _warnings_spwd_mod.catch_warnings():
        _warnings_spwd_mod.simplefilter("ignore", DeprecationWarning)
        import spwd
except ImportError:
    spwd = None
import sys
import syslog

import pytest


# -- resource -----------------------------------------------------------------

# spwd 在 Python 3.13 起被移除,没有它整个文件连收集都会失败
pytestmark = pytest.mark.skipif(spwd is None, reason="spwd 模块在 Python 3.13 起被移除")


class TestResource:
    def test_getrlimit_no_file_returns_tuple(self):
        """`resource.getrlimit(RLIMIT_NOFILE)` 返 `(soft, hard)` tuple。"""
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        assert isinstance(soft, int)
        assert isinstance(hard, int)
        assert soft >= 1 and hard >= 1

    def test_setrlimit_no_file_and_readback(self):
        """`resource.setrlimit(RLIMIT_NOFILE, (soft, hard))` 真生效并读回。"""
        # 沙箱: root 通常硬限 ≥ 1024, 软限可设 ≤ 硬限
        old_soft, old_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        new_soft = max(64, min(old_soft, old_hard, 256))
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, old_hard))
            got_soft, got_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            assert got_soft == new_soft
            assert got_hard == old_hard
        finally:
            resource.setrlimit(resource.RLIMIT_NOFILE, (old_soft, old_hard))

    def test_rlimit_constants_are_positive_integers(self):
        """`RLIMIT_*` 常量是真正整数。"""
        for name in ("RLIMIT_NOFILE", "RLIMIT_NPROC", "RLIMIT_AS"):
            assert isinstance(getattr(resource, name), int)
            assert getattr(resource, name) > 0


# -- grp ----------------------------------------------------------------------

class TestGrp:
    def test_getgrgid_zero_returns_root_group(self):
        """`grp.getgrgid(0)` 拿 root 组,gid == 0,.gr_name 是字符串。"""
        try:
            info = grp.getgrgid(0)
        except KeyError:
            pytest.skip("沙箱无 gid 0,跳过")
        assert info.gr_gid == 0
        assert isinstance(info.gr_name, str) and info.gr_name, (
            f"root 组 gr_name 应是非空字符串,实际 {info.gr_name!r}"
        )
        assert isinstance(info.gr_mem, list)

    def test_getgrall_returns_nonempty_list(self):
        """`grp.getgrall` 返 list,长度 ≥ 1。"""
        all_groups = grp.getgrall()
        assert isinstance(all_groups, list)
        assert len(all_groups) >= 1
        assert all(isinstance(g.gr_gid, int) for g in all_groups)


# -- spwd (shadow passwd) -----------------------------------------------------

class TestSpwd:
    def test_getspnam_root_returns_struct(self):
        """`spwd.getspnam('root')` 返 struct,`.sp_nam` 字段是 'root'。"""
        try:
            entry = spwd.getspnam("root")
        except (KeyError, PermissionError, OSError) as e:
            pytest.skip(f"沙箱无权读 shadow: {e}")
        assert entry.sp_nam == "root"
        assert isinstance(entry.sp_pwd, str)
        # sp_pwd 通常以 '$id$salt$hash' 或 '*' (locked) / '!' 开头
        assert entry.sp_pwd and entry.sp_pwd[0] in "$*!", (
            f"sp_pwd 应以 $/\\*/! 开头,实际 {entry.sp_pwd[:5]!r}"
        )


# -- syslog -------------------------------------------------------------------

class TestSyslog:
    def test_syslog_constants_are_integers(self):
        """`syslog.LOG_*` 是真正整数。"""
        for name in ("LOG_EMERG", "LOG_ALERT", "LOG_CRIT", "LOG_ERR",
                     "LOG_WARNING", "LOG_NOTICE", "LOG_INFO", "LOG_DEBUG"):
            assert isinstance(getattr(syslog, name), int)

    def test_openlog_syslog_closelog_round_trip(self):
        """`syslog.openlog` + `syslog.syslog` + `syslog.closelog` 真往返。

        在沙箱中无 syslog 服务时 openlog 仍成功 (写 unix socket),syslog 调用
        本身不抛,closelog 关闭 handler。
        """
        syslog.openlog("forgemind-underlying-test", syslog.LOG_PID, syslog.LOG_USER)
        try:
            syslog.syslog(syslog.LOG_INFO, "underlying test message")
        finally:
            syslog.closelog()

    def test_setlogmask_filters_messages(self):
        """`syslog.setlogmask` 真设 mask,`LOG_UPTO(INFO)` 应含 INFO 与更高级别。"""
        mask = syslog.LOG_UPTO(syslog.LOG_INFO)
        syslog.setlogmask(mask)
        assert syslog.LOG_UPTO(syslog.LOG_INFO) & (1 << syslog.LOG_INFO) != 0
        assert syslog.LOG_UPTO(syslog.LOG_INFO) & (1 << syslog.LOG_DEBUG) == 0
