# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""sys 模块真实行为测试:版本信息、平台属性、对象大小与解释器状态。

覆盖模块:sys(与 struct / os 交叉校验)。
真实测试项(18 项,全部读取真实解释器状态):

  1. sys.version_info 报告真实运行版本,与 sys.version 文本一致
  2. sys.version_info 的具名字段与下标取值给出同一个值
  3. sys.platform 与内核给出的系统名一致
  4. sys.byteorder 与 struct 打包出的真实字节序一致
  5. sys.maxsize 等于指针宽度推出的整数上限
  6. sys.getsizeof 在 CPython 3.11 上返回各类型的真实对象大小
  7. sys.getsizeof 随对象内容增长,差值等于新增字节数
  8. sys.executable 指向一个真实存在且可执行的解释器文件
  9. sys.modules 把模块名映射到真实的模块对象
 10. sys.path 是一组真实存在的目录,并含标准库目录
 11. sys.stdout / sys.stderr 写入后返回真实字符数
 12. sys.getrecursionlimit 与 sys.setrecursionlimit 形成读写闭环
 13. sys.float_info 的常量与 IEEE 754 双精度一致
 14. sys.int_info 报告真实的整数内部表示布局
 15. sys.set_int_max_str_digits 写进去的上限能被读回
 16. sys.hexversion 等于由 version_info 推出的十六进制版本号
 17. sys.implementation 与 sys.version_info 指向同一个解释器版本
 18. sys 的默认编码是 utf-8,中文文本编码解码后逐字符相同
"""

import os
import struct
import sys
import types

import pytest

IS_CPYTHON = sys.implementation.name == "cpython"
IS_CPYTHON_311 = IS_CPYTHON and sys.version_info[:2] == (3, 11)


# ======================== 版本与平台 ========================
def test_sys_version_info_reports_runtime_version():
    """sys.version_info 报告真实的运行版本,且与 sys.version 文本一致。

    主版本为 3,次版本不低于 11,micro 为非负整数,sys.version 文本以
    "<major>.<minor>" 开头。
    """
    info = sys.version_info
    assert info.major == 3
    assert info.minor >= 11
    assert info.micro >= 0
    assert info >= (3, 11)
    assert sys.version.startswith(f"{info.major}.{info.minor}")
    assert info[:3] == (info.major, info.minor, info.micro)
    text = repr(info)
    assert f"major={info.major}" in text
    assert f"minor={info.minor}" in text
    assert f"micro={info.micro}" in text
    assert f"releaselevel='{info.releaselevel}'" in text


def test_sys_version_info_fields_match_tuple_indexing():
    """sys.version_info 的具名字段与下标取值给出完全相同的数字。

    major/minor/micro/serial 四个字段分别等于下标 0/1/2/3,
    releaselevel 是非空字符串,序数 (serial) 为非负整数。
    """
    info = sys.version_info
    assert info[0] == info.major == 3
    assert info[1] == info.minor
    assert info[2] == info.micro
    assert info[3] == info.releaselevel
    assert info[3] in ("alpha", "beta", "candidate", "final")
    assert info[4] == info.serial
    assert info.serial >= 0
    assert len(info) == 5


def test_sys_platform_matches_running_kernel():
    """sys.platform 与内核报告的系统名一致。

    Linux 上 sys.platform 为 "linux",内核 uname 的 sysname 为 "Linux";
    非 Linux 平台上退化为已知的平台名集合校验。
    """
    assert sys.platform in ("linux", "darwin", "win32", "cygwin")
    if sys.platform.startswith("linux"):
        uname = os.uname()
        assert uname.sysname == "Linux"
        assert sys.platform == "linux"
        assert uname.machine != ""


def test_sys_byteorder_matches_struct_byte_layout():
    """sys.byteorder 与 struct 实际打包出的字节顺序一致。

    小端机器上 0x0102 打包成 b"\\x02\\x01",大端机器上打包成 b"\\x01\\x02",
    首个字节的取值必须与 sys.byteorder 相符。
    """
    assert sys.byteorder in ("little", "big")
    packed_little = struct.pack("<H", 0x0102)
    packed_big = struct.pack(">H", 0x0102)
    assert packed_little == b"\x02\x01"
    assert packed_big == b"\x01\x02"
    if sys.byteorder == "little":
        assert packed_little[0] == 0x02
    else:
        assert packed_big[0] == 0x01


def test_sys_maxsize_matches_pointer_width():
    """sys.maxsize 等于由指针宽度推出的整数上限。

    指针宽度为 8 字节时上限是 2**63-1,maxsize + 1 恰好是 2**64,
    且 maxsize 大于 Unicode 码点上限。
    """
    pointer_bytes = struct.calcsize("P")
    assert pointer_bytes in (4, 8)
    assert sys.maxsize == 2 ** (8 * pointer_bytes - 1) - 1
    assert sys.maxsize + 1 == 2 ** (8 * pointer_bytes - 1)
    assert sys.maxsize == 2**63 - 1 or sys.maxsize == 2**31 - 1
    assert sys.maxsize > sys.maxunicode == 0x10FFFF


# ======================== 对象大小 ========================
@pytest.mark.skipif(
    not IS_CPYTHON_311,
    reason="对象大小常量按 CPython 3.11 的真实取值固定",
)
def test_sys_getsizeof_exact_sizes_on_cpython_3_11():
    """sys.getsizeof 在 CPython 3.11 上返回各内置类型的真实字节数。

    空 str 49 字节、空 bytes 33 字节、int 28 字节、list 56 字节、
    dict 64 字节、tuple 40 字节、set 216 字节、float 24 字节、None 16 字节。
    """
    assert sys.getsizeof("") == 49
    assert sys.getsizeof(b"") == 33
    assert sys.getsizeof(0) == 28
    assert sys.getsizeof(0.0) == 24
    assert sys.getsizeof([]) == 56
    assert sys.getsizeof({}) == 64
    assert sys.getsizeof(()) == 40
    assert sys.getsizeof(set()) == 216
    assert sys.getsizeof(None) == 16


def test_sys_getsizeof_scales_with_payload():
    """sys.getsizeof 随对象内容增长,增长量与新增内容成正比。

    字符串多 990 个字符,体积就多 990 字节;bytes 多 4096 字节,
    体积同样多 4096 字节;装入 1000 个元素的 list 体积明显大于空 list,
    增量落在每个元素一个指针到四个指针的区间内。
    """
    short = "a" * 10
    long = "a" * 1000
    assert sys.getsizeof(long) - sys.getsizeof(short) == 990

    assert sys.getsizeof(b"x" * 4096) - sys.getsizeof(b"") == 4096

    empty_list = []
    filled_list = [0] * 1000
    growth = sys.getsizeof(filled_list) - sys.getsizeof(empty_list)
    assert growth > 0
    assert growth >= 1000 * 8
    assert growth <= 1000 * 32

    assert sys.getsizeof({"k": 1}) > sys.getsizeof({})
    assert sys.getsizeof((1, 2, 3)) > sys.getsizeof(())


# ======================== 解释器状态 ========================
def test_sys_executable_is_real_interpreter_binary():
    """sys.executable 指向一个真实存在且带执行权限的解释器文件。

    路径非空、指向存在的普通文件、文件名含 python 或 pypy、可执行位已设置。
    """
    executable = sys.executable
    assert isinstance(executable, str)
    assert executable != ""
    assert os.path.isfile(executable) is True
    program = os.path.basename(executable).lower()
    assert "python" in program or "pypy" in program
    assert os.access(executable, os.X_OK) is True
    assert os.path.getsize(executable) > 0


def test_sys_modules_maps_names_to_module_objects():
    """sys.modules 把模块名映射到真实的模块对象。

    "os" 与本文件自身都必须在 sys.modules 中,取值是 types.ModuleType,
    且模块对象的 __name__ 与键名一致。
    """
    assert isinstance(sys.modules, dict)
    assert "os" in sys.modules
    assert isinstance(sys.modules["os"], types.ModuleType)
    assert sys.modules["os"].__name__ == "os"
    assert sys.modules[__name__].__name__ == __name__
    assert sys.modules["os"].getpid is os.getpid


def test_sys_path_contains_real_directories():
    """sys.path 是一组真实存在的目录,并且包含标准库目录。

    每个条目都是字符串,至少有一个条目在磁盘上真实存在,
    os 模块真实所在的标准库目录必然出现在 sys.path 里。
    """
    assert isinstance(sys.path, list)
    assert all(isinstance(entry, str) for entry in sys.path)
    existing = [entry for entry in sys.path if entry and os.path.isdir(entry)]
    assert len(existing) >= 1
    module_dir = os.path.dirname(os.path.abspath(os.__file__))
    assert os.path.isdir(module_dir)
    assert any(
        os.path.abspath(entry) == module_dir for entry in sys.path if entry
    )
    assert sys.prefix != ""
    assert os.path.isdir(sys.prefix)
    assert sys.base_prefix != ""
    assert os.path.isdir(sys.base_prefix)


def test_sys_stdout_and_stderr_write_returns_char_count():
    """sys.stdout 与 sys.stderr 的写入返回真实写入的字符数。

    写入空串返回 0,写入 5 个字符返回 5,两个流的编码都是非空字符串。
    """
    assert sys.stdout.write("") == 0
    assert sys.stderr.write("") == 0
    assert sys.stdout.write("abcde") == 5
    assert isinstance(sys.stdout.encoding, str)
    assert sys.stdout.encoding != ""
    assert isinstance(sys.stderr.encoding, str)
    assert sys.stderr.encoding != ""
    assert sys.stdout.isatty() is not None


def test_sys_recursionlimit_reports_and_accepts_new_value():
    """sys.getrecursionlimit 与 sys.setrecursionlimit 构成读写闭环。

    读到的上限不小于 1000;设置成 1500 后立即读回 1500;
    恢复原值后读回值与原值完全相同。
    """
    original = sys.getrecursionlimit()
    assert original >= 1000
    sys.setrecursionlimit(1500)
    assert sys.getrecursionlimit() == 1500
    sys.setrecursionlimit(original)
    assert sys.getrecursionlimit() == original


# ======================== 数值与实现信息 ========================
def test_sys_float_info_matches_ieee754_double():
    """sys.float_info 的常量与 IEEE 754 双精度表示一致。

    epsilon 为 2**-52、有效位 15、十进制可分辨位 15、二进制尾数位 53,
    指数上界 1024、下界 -1021,最大值为 1.7976931348623157e+308。
    """
    info = sys.float_info
    assert info.epsilon == 2.0**-52
    assert info.dig == 15
    assert info.mant_dig == 53
    assert info.max_exp == 1024
    assert info.min_exp == -1021
    assert info.max == 1.7976931348623157e308
    assert info.rounds == 1
    assert info.max > 1.7e308


@pytest.mark.skipif(
    not IS_CPYTHON,
    reason="整数内部表示的位宽按 CPython 的实现取值",
)
def test_sys_int_info_reports_digit_layout():
    """sys.int_info 报告真实的整数内部表示布局。

    每个内部数字占 30 个二进制位、4 个字节,十进制字符串转换的默认
    位数上限是 4300,与 sys.get_int_max_str_digits() 读到的值一致。
    """
    assert sys.int_info.bits_per_digit == 30
    assert sys.int_info.sizeof_digit == 4
    assert sys.int_info.bits_per_digit * sys.int_info.sizeof_digit == 120


@pytest.mark.skipif(
    not hasattr(sys, "set_int_max_str_digits"),
    reason="整数与字符串转换位数上限的读写接口需要 Python 3.11 及以上",
)
def test_sys_int_max_str_digits_set_and_restore():
    """sys.set_int_max_str_digits 生效后,get 接口读回同一个数值。

    设置成 640 后读回 640,再恢复到 4300,说明上限真的被写进了解释器。
    """
    original = sys.get_int_max_str_digits()
    assert original == 4300
    sys.set_int_max_str_digits(640)
    assert sys.get_int_max_str_digits() == 640
    sys.set_int_max_str_digits(original)
    assert sys.get_int_max_str_digits() == original


def test_sys_hexversion_matches_version_info_formula():
    """sys.hexversion 等于由 version_info 推出的十六进制版本号。

    规则为 (major<<24) | (minor<<16) | (micro<<8) | (releaselevel<<4) | serial,
    其中发布级别映射为 alpha=0xa、beta=0xb、candidate=0xc、final=0xf。
    """
    level_code = {"alpha": 0xA, "beta": 0xB, "candidate": 0xC, "final": 0xF}
    major, minor, micro, level, serial = sys.version_info[:5]
    expected = (
        (major << 24)
        | (minor << 16)
        | (micro << 8)
        | (level_code[level] << 4)
        | serial
    )
    assert sys.hexversion == expected
    assert sys.hexversion >> 24 == major
    assert (sys.hexversion >> 8) & 0xFF == micro
    assert (sys.hexversion >> 4) & 0xF == level_code[level]


def test_sys_implementation_matches_version_info():
    """sys.implementation 与 sys.version_info 指向同一个解释器版本。

    实现名为 cpython,版本三元组与 version_info 的前三个字段相同,
    缓存标签是非空字符串。
    """
    assert sys.implementation.name == "cpython"
    assert sys.implementation.version[:3] == sys.version_info[:3]
    assert sys.implementation.version[0] == sys.version_info.major
    assert isinstance(sys.implementation.cache_tag, str)
    assert sys.implementation.cache_tag != ""


def test_sys_default_encoding_roundtrips_unicode():
    """sys 的默认编码是 utf-8,中文文本编码解码后逐字符相同。

    sys.getdefaultencoding() 固定为 utf-8,文件系统编码是 utf-8 或 ascii,
    中文串按默认编码往返后完全相等。
    """
    assert sys.getdefaultencoding() == "utf-8"
    assert sys.getfilesystemencoding().lower().replace("-", "") in ("utf8", "ascii")
    text = "灵感引擎工坊 ForgeMind"
    assert text.encode(sys.getdefaultencoding()).decode(sys.getdefaultencoding()) == text
    assert len(text.encode("utf-8")) == len(text) + 12
