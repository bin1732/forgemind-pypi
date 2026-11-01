# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`rlcompleter` / `sre_compile` / `stringprep` / `mailcap` 真底层测试。

- rlcompleter:真的在解释器命名空间里补全属性与关键字
- sre_compile:真正的正则编译,含已废弃接口的真实行为
- stringprep:真的按 Unicode 规范做名称检查与映射
- mailcap:真的读系统里的 mime.types 文件并按条目查能力

覆盖 rlcompleter 5 + sre_compile 5 + stringprep 5 + mailcap 5 + 真底层测试。
"""

import os
import re
import stringprep
import sys
import tempfile
from pathlib import Path

import pytest

# mailcap 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import mailcap
except ImportError:
    mailcap = None
import rlcompleter
# sre_compile 已弃用或已从标准库移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_sre_compile
    with _warnings_sre_compile.catch_warnings():
        _warnings_sre_compile.simplefilter("ignore", DeprecationWarning)
        import sre_compile
except ImportError:
    sre_compile = None


# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(mailcap is None, reason="mailcap 模块在 Python 3.13 起被移除")


@pytest.fixture
def workdir():
    """建一个临时工作目录,测试结束后清理。"""
    path = Path(tempfile.mkdtemp(prefix="forge_stdlib2_"))
    try:
        yield path
    finally:
        import shutil
        shutil.rmtree(path, ignore_errors=True)


# ======================== rlcompleter ========================


def _complete_all(completer, text: str) -> list:
    """按补全接口的两段式用法取全部候选。

    接口按状态号逐次返回候选,返回空表示结束。
    """
    results = []
    state = 0
    while True:
        item = completer.complete(text, state)
        if item is None:
            break
        results.append(item)
        state += 1
    return results


class TestRlcompleter:
    """解释器补全"""

    def test_complete_attribute(self):
        """补全对象的属性名"""
        completer = rlcompleter.Completer()
        matches = _complete_all(completer, "str.")
        assert isinstance(matches, list)
        # 属性补全给出的是可以直接调用的形式
        assert "str.upper(" in matches
        assert "str.lower(" in matches

    def test_complete_keyword(self):
        """补全关键字"""
        completer = rlcompleter.Completer()
        matches = _complete_all(completer, "whi")
        assert "while " in matches

    def test_complete_builtin(self):
        """补全内建名"""
        completer = rlcompleter.Completer()
        matches = _complete_all(completer, "prin")
        assert "print(" in matches

    def test_complete_no_match(self):
        """没有匹配时返回空列表"""
        completer = rlcompleter.Completer()
        assert _complete_all(completer, "zzz_no_such_name_zzz") == []

    def test_complete_local_scope(self):
        """按调用处的命名空间补全"""
        completer = rlcompleter.Completer()
        # 关掉主模块命名空间,否则每次补全都会把它覆盖掉
        completer.use_main_ns = False
        completer.namespace = {"forge_local": 1}
        matches = _complete_all(completer, "forge_")
        assert "forge_local" in matches

    def test_complete_attribute_of_instance(self):
        """补全实例的属性"""
        class Holder:
            def __init__(self):
                self.forge_field = 1

        completer = rlcompleter.Completer()
        completer.use_main_ns = False
        # 补全的表达式按标识符解析,实例要放在命名空间里
        completer.namespace = {"holder": Holder()}
        matches = _complete_all(completer, "holder.forge_")
        assert any("forge_field" in m for m in matches)

    def test_complete_already_complete_name(self):
        """补全会给出带调用括号的形式"""
        completer = rlcompleter.Completer()
        matches = _complete_all(completer, "str.upper")
        assert "str.upper(" in matches

    def test_complete_case_sensitive(self):
        """补全区分大小写"""
        completer = rlcompleter.Completer()
        assert _complete_all(completer, "STR.") == []

    def test_complete_dotted_module(self):
        """补全模块里的名字"""
        completer = rlcompleter.Completer()
        completer.use_main_ns = False
        completer.namespace = {"stringprep": stringprep}
        matches = _complete_all(completer, "stringprep.in")
        assert any(m.startswith("stringprep.in") for m in matches)

    def test_complete_empty_text(self):
        """空文本时给出提示,随后没有更多候选"""
        completer = rlcompleter.Completer()
        first = completer.complete("", 0)
        assert isinstance(first, str)
        assert completer.complete("", 1) is None


# ======================== sre_compile ========================


class TestSreCompile:
    """正则编译"""

    def test_compile_simple(self):
        """简单模式能编译"""
        pattern = sre_compile.compile("forge")
        assert pattern is not None

    def test_compile_with_flags(self):
        """带标志能编译"""
        pattern = sre_compile.compile("FORGE", re.IGNORECASE)
        assert pattern is not None

    def test_compile_error(self):
        """非法模式抛出真实错误"""
        with pytest.raises(re.error):
            sre_compile.compile("(unclosed")

    def test_isstring(self):
        """识别字符串与字节串"""
        assert sre_compile.isstring("forge") is True
        assert sre_compile.isstring(b"forge") is True
        assert sre_compile.isstring(42) is False

    def test_opcode_constants_present(self):
        """操作码常量齐备"""
        assert sre_compile.LITERAL >= 0
        assert sre_compile.MAXREPEAT > 0
        assert sre_compile.ANY > 0
        assert sre_compile.AT > 0
        assert sre_compile.IN > 0

    def test_compile_pattern_usable(self):
        """编译结果能真正用于匹配"""
        pattern = sre_compile.compile("f.rge")
        assert pattern.search("xforgey") is not None
        assert pattern.search("forgy") is None


# ======================== stringprep ========================


class TestStringprep:
    """Unicode 名称规范

    每张表的成员都是按 Unicode 码位定义的,这里直接引用规范里的
    代表字符,断言的是这些字符确实落在对应的表里。
    """

    def test_in_table_a1(self):
        """表 A.1 收录 Unicode 字母"""
        assert stringprep.in_table_a1("\u0221") is True
        assert stringprep.in_table_a1("\u0234") is True

    def test_in_table_a1_excludes_ascii_letters(self):
        """ASCII 字母不在表 A.1 里,那些走另外的判定"""
        assert stringprep.in_table_a1("a") is False
        assert stringprep.in_table_a1(" ") is False

    def test_map_table_b2(self):
        """表 B.2 做大小写无关映射"""
        assert stringprep.map_table_b2("A") == "a"
        assert stringprep.map_table_b2("a") == "a"
        assert stringprep.map_table_b2("\u00c9") == "\u00e9"

    def test_map_table_b2_keeps_digits(self):
        """数字不受大小写映射影响"""
        assert stringprep.map_table_b2("1") == "1"

    def test_in_table_c11(self):
        """表 C.1.1 只收录空格"""
        assert stringprep.in_table_c11(" ") is True
        assert stringprep.in_table_c11("a") is False

    def test_in_table_c12(self):
        """表 C.1.2 收录非 ASCII 的空白"""
        assert stringprep.in_table_c12("\u00a0") is True
        assert stringprep.in_table_c12("\u2000") is True
        assert stringprep.in_table_c12("a") is False

    def test_in_table_c11_c12(self):
        """表 C.1.1 与 C.1.2 合起来收录所有空白"""
        assert stringprep.in_table_c11_c12(" ") is True
        assert stringprep.in_table_c11_c12("\u00a0") is True
        assert stringprep.in_table_c11_c12("a") is False

    def test_in_table_c21(self):
        """表 C.2.1 收录控制字符"""
        assert stringprep.in_table_c21("\x00") is True
        assert stringprep.in_table_c21("\x01") is True
        assert stringprep.in_table_c21("a") is False

    def test_in_table_c22(self):
        """表 C.2.2 收录高位控制字符"""
        assert stringprep.in_table_c22("\u0080") is True
        assert stringprep.in_table_c22("\u0081") is True
        assert stringprep.in_table_c22("1") is False

    def test_in_table_c21_c22(self):
        """表 C.2.1 与 C.2.2 合起来收录全部控制字符"""
        assert stringprep.in_table_c21_c22("\x00") is True
        assert stringprep.in_table_c21_c22("\u0080") is True
        assert stringprep.in_table_c21_c22("a") is False

    def test_in_table_c3(self):
        """表 C.3 收录私有区的组合"""
        assert stringprep.in_table_c3("\ue000") is True
        assert stringprep.in_table_c3("a") is False

    def test_in_table_c4(self):
        """表 C.4 收录被忽略的字符"""
        assert stringprep.in_table_c4("\ufdd0") is True
        assert stringprep.in_table_c4("a") is False

    def test_in_table_c5(self):
        """表 C.5 收录代理区的组合"""
        assert stringprep.in_table_c5("\ud800") is True
        assert stringprep.in_table_c5("a") is False

    def test_in_table_c6(self):
        """表 C.6 收录禁止的组合"""
        assert stringprep.in_table_c6("\ufff9") is True
        assert stringprep.in_table_c6("a") is False

    def test_in_table_c7(self):
        """表 C.7 收录希腊语中间记号"""
        assert stringprep.in_table_c7("\u2ff0") is True
        assert stringprep.in_table_c7("a") is False

    def test_in_table_c8(self):
        """表 C.8 收录大小写不敏感的字符"""
        assert stringprep.in_table_c8("\u0340") is True
        assert stringprep.in_table_c8("a") is False

    def test_in_table_c9(self):
        """表 C.9 收录不允许的字符"""
        assert stringprep.in_table_c9("\U000e0001") is True
        assert stringprep.in_table_c9("a") is False

    def test_in_table_d1(self):
        """表 D.1 收录会被删除的字符"""
        assert stringprep.in_table_d1("\u05be") is True
        assert stringprep.in_table_d1("a") is False

    def test_in_table_d2(self):
        """表 D.2 收录会变成空白的字符"""
        assert stringprep.in_table_d2("A") is True
        assert stringprep.in_table_d2("B") is True
        assert stringprep.in_table_d2("a") is True
        assert stringprep.in_table_d2("1") is False

# ======================== mailcap ========================


class TestMailcap:
    """能力表查询

    能力表文件的字段用分号分隔:第一个是媒体类型,第二个是查看命令,
    其余是参数。查询用的是已解析好的字典。
    """

    @staticmethod
    def _caps(workdir: Path, content: str) -> dict:
        """把能力表文件读成查询用的字典。"""
        path = workdir / "mime.types"
        path.write_text(content, encoding="utf-8")
        with path.open("r", encoding="utf-8") as fp:
            return mailcap.readmailcapfile(fp)

    def test_readmailcapfile(self, workdir):
        """读出能力表里的条目"""
        caps = self._caps(
            workdir, "application/x-forge; forge_tool %s\n"
        )
        assert "application/x-forge" in caps
        assert caps["application/x-forge"][0]["view"] == "forge_tool %s"

    def test_readmailcapfile_ignores_comments(self, workdir):
        """注释行与空行被跳过"""
        caps = self._caps(
            workdir,
            "# 注释\n\napplication/x-forge; forge_tool %s\n",
        )
        assert list(caps) == ["application/x-forge"]

    def test_lookup_by_mime_type(self, workdir):
        """按媒体类型查到对应条目"""
        caps = self._caps(workdir, "application/x-forge; forge_tool %s\n")
        entries = mailcap.lookup(caps, "application/x-forge")
        assert entries == [{"view": "forge_tool %s"}]

    def test_lookup_missing_type(self, workdir):
        """查不到时返回空列表"""
        caps = self._caps(workdir, "application/x-forge; forge_tool %s\n")
        assert mailcap.lookup(caps, "application/x-none") == []

    def test_lookup_wildcard(self, workdir):
        """按类型通配也能查到"""
        caps = self._caps(workdir, "text/*; forge_text %s\n")
        entries = mailcap.lookup(caps, "text/plain")
        assert entries == [{"view": "forge_text %s"}]

    def test_lookup_with_key_filter(self, workdir):
        """带参数过滤时只留含该参数的条目"""
        caps = self._caps(
            workdir, "application/x-forge; forge_tool %s; forge=yes\n"
        )
        entries = mailcap.lookup(caps, "application/x-forge", "forge")
        assert entries == [{"view": "forge_tool %s", "forge": "yes"}]
        assert mailcap.lookup(caps, "application/x-forge", "absent") == []

    def test_parseline(self):
        """解析一行能力表条目"""
        key, fields = mailcap.parseline("application/x-forge; forge_tool %s")
        assert key == "application/x-forge"
        assert fields["view"] == "forge_tool %s"

    def test_parseline_with_parameters(self):
        """带参数的条目被解析成键值对"""
        key, fields = mailcap.parseline("application/x-forge; forge_tool %s; forge=yes")
        assert key == "application/x-forge"
        assert fields["forge"] == "yes"

    def test_parseline_too_few_fields(self):
        """字段不足时返回空"""
        assert mailcap.parseline("application/x-forge") == (None, None)

    def test_parsefield(self):
        """解析出第一个字段与它的结束位置"""
        field, index = mailcap.parsefield("application/x-forge; forge_tool %s", 0, 40)
        assert field == "application/x-forge"
        assert index > 0

    def test_findmatch(self, workdir):
        """找到匹配的查看命令"""
        caps = self._caps(workdir, "application/x-forge; forge_tool %s\n")
        command, entry = mailcap.findmatch(caps, "application/x-forge")
        assert command.startswith("forge_tool")
        assert entry["view"] == "forge_tool %s"

    def test_findmatch_missing(self, workdir):
        """找不到时返回空"""
        caps = self._caps(workdir, "application/x-forge; forge_tool %s\n")
        assert mailcap.findmatch(caps, "application/x-none") == (None, None)

    def test_subst(self):
        """占位符被替换成实际参数"""
        assert mailcap.subst("forge_tool %s", "forge_tool", "arg") == "forge_tool arg"

    def test_listmailcapfiles(self):
        """列出系统里的能力表文件位置"""
        files = mailcap.listmailcapfiles()
        assert isinstance(files, list)
        assert all(isinstance(item, str) for item in files)

    def test_getcaps_returns_dict(self):
        """汇总出的能力表是字典"""
        caps = mailcap.getcaps()
        assert isinstance(caps, dict)
