# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""locale 方向的底层真实行为测试:编码协商、数字格式化、locale 查询与排序行为。

覆盖模块:locale(标准库,POSIX locale 接口的 Python 封装)。

真实测试项(共 18 个):
  1. getpreferredencoding 在 UTF-8 模式下真实返回 "utf-8"
  2. C locale 下 getencoding 解析出的编码名是 ascii
  3. C.UTF-8 locale 下 getencoding 解析出的编码名是 utf-8
  4. C locale 下 getlocale 真实返回 (None, None)
  5. C.UTF-8 locale 下 getlocale 真实返回 ("en_US", "UTF-8")
  6. getlocale 传入 LC_ALL 抛 TypeError
  7. setlocale 传入不存在的 locale 名抛 locale.Error
  8. setlocale(LC_ALL) 一次性切换全部 locale 类别
  9. format_string 真实产出精度与宽度对齐的字符串
 10. format_string 在 C locale 下不插入千位分隔符
 11. format_string 支持字典形式的命名占位符
 12. delocalize/localize 遵循当前 locale 的数字约定
 13. strxfrm 产出排序键,C locale 下按字节序排列
 14. strcoll 按当前 locale 的排序规则给出 -1/0/1
 15. currency 在 C locale 下抛 ValueError
 16. nl_langinfo 的 CODESET 跟随 LC_CTYPE 变化
 17. locale_alias 别名表与 normalize 的归一化结果
 18. getdefaultlocale 触发 DeprecationWarning 且不受 setlocale 影响

沙箱只提供 C / C.UTF-8 / POSIX 三种 locale。依赖 C.UTF-8 的用例在系统缺少该
locale 时用 skipif 跳过,并在跳过原因里写明缺的是什么。
"""

import codecs
import locale
import re
import sys

import pytest

# 文件加载时的 locale 设置,每个用例结束后恢复,避免用例之间互相污染。
_ORIGINAL_LOCALE = locale.setlocale(locale.LC_ALL)

# locale.getdefaultlocale 在 3.11 起弃用,3.13 起被移除。
HAS_GETDEFAULTLOCALE = hasattr(locale, "getdefaultlocale")


def _locale_is_available(name: str) -> bool:
    """检查目标 locale 是否被当前系统接受,检查结束后恢复原设置。"""
    current = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, name)
    except locale.Error:
        return False
    finally:
        locale.setlocale(locale.LC_ALL, current)
    return True


# C.UTF-8 是本机唯一带编码标记的 locale,拿不到时相关用例直接跳过。
C_UTF8_AVAILABLE = _locale_is_available("C.UTF-8")

requires_c_utf8 = pytest.mark.skipif(
    not C_UTF8_AVAILABLE,
    reason="系统未提供 C.UTF-8 locale,跳过依赖该 locale 的用例",
)

requires_codeset = pytest.mark.skipif(
    not hasattr(locale, "CODESET"),
    reason="当前平台没有 locale.CODESET 常量,跳过 nl_langinfo 用例",
)


@pytest.fixture(autouse=True)
def _restore_locale_setting():
    """每个用例结束后把 locale 恢复到文件加载时的状态。"""
    yield
    locale.setlocale(locale.LC_ALL, _ORIGINAL_LOCALE)


class TestLocaleEncoding:
    """编码协商相关行为。"""

    def test_getpreferredencoding_reports_utf8_under_utf8_mode(self):
        """UTF-8 模式下 getpreferredencoding 的两个参数都真实返回 "utf-8"。"""
        encoding = locale.getpreferredencoding(False)
        if sys.flags.utf8_mode:
            assert encoding == "utf-8"
            assert locale.getpreferredencoding(True) == "utf-8"
        else:
            assert encoding == locale.getencoding()
        assert codecs.lookup(encoding).name == "utf-8"

    def test_getencoding_reports_ascii_codeset_under_c_locale(self):
        """C locale 下 getencoding 拿到的编码名解析后是 ascii。"""
        locale.setlocale(locale.LC_ALL, "C")
        encoding = locale.getencoding()
        assert encoding != "UTF-8"
        assert codecs.lookup(encoding).name == "ascii"

    @requires_c_utf8
    def test_getencoding_reports_utf8_codeset_under_c_utf8_locale(self):
        """切到 C.UTF-8 locale 后 getencoding 拿到的编码名解析后是 utf-8。"""
        locale.setlocale(locale.LC_ALL, "C.UTF-8")
        encoding = locale.getencoding()
        assert encoding == "UTF-8"
        assert codecs.lookup(encoding).name == "utf-8"


class TestLocaleQuery:
    """getlocale / setlocale 的真实返回与错误行为。"""

    def test_getlocale_returns_none_pair_under_c_locale(self):
        """C locale 下 getlocale 真实返回 (None, None),各类别都如此。"""
        locale.setlocale(locale.LC_ALL, "C")
        assert locale.getlocale() == (None, None)
        assert locale.getlocale(locale.LC_CTYPE) == (None, None)
        assert locale.getlocale(locale.LC_NUMERIC) == (None, None)

    @requires_c_utf8
    def test_getlocale_reports_utf8_pair_under_c_utf8_locale(self):
        """C.UTF-8 locale 下 getlocale 真实返回 ("en_US", "UTF-8")。

        这个取值来自 CPython 的 locale_alias 表:别名 c.utf8 被映射成
        en_US.UTF-8,getlocale 解析该名字后给出语言与编码两段。
        """
        locale.setlocale(locale.LC_ALL, "C.UTF-8")
        assert locale.getlocale() == ("en_US", "UTF-8")
        assert locale.getlocale(locale.LC_CTYPE) == ("en_US", "UTF-8")

    @requires_c_utf8
    def test_getlocale_rejects_lc_all_category(self):
        """类别设置不一致时 LC_ALL 查询返回复合串,getlocale(LC_ALL) 抛 TypeError。"""
        locale.setlocale(locale.LC_ALL, "C")
        locale.setlocale(locale.LC_NUMERIC, "C.UTF-8")
        composite = locale.setlocale(locale.LC_ALL)
        assert ";" in composite
        assert "LC_NUMERIC=C.UTF-8" in composite
        with pytest.raises(TypeError, match="category LC_ALL is not supported"):
            locale.getlocale(locale.LC_ALL)

    def test_setlocale_rejects_unknown_locale_name(self):
        """setlocale 传入系统不认识的 locale 名抛 locale.Error。"""
        with pytest.raises(locale.Error, match="unsupported locale setting"):
            locale.setlocale(locale.LC_ALL, "xx_YY.INVALID")

    @requires_c_utf8
    def test_setlocale_switches_all_categories_together(self):
        """setlocale(LC_ALL, ...) 一次性切换全部类别,查询结果同步变化。"""
        locale.setlocale(locale.LC_ALL, "C")
        assert locale.setlocale(locale.LC_CTYPE) == "C"
        locale.setlocale(locale.LC_ALL, "C.UTF-8")
        assert locale.setlocale(locale.LC_CTYPE) == "C.UTF-8"
        assert locale.setlocale(locale.LC_NUMERIC) == "C.UTF-8"
        assert locale.setlocale(locale.LC_TIME) == "C.UTF-8"


class TestLocaleNumberFormatting:
    """format_string / delocalize / localize 的真实格式化结果。"""

    def test_format_string_applies_precision_and_width(self):
        """format_string 真实产出按精度截断、按宽度补齐的字符串。"""
        assert locale.format_string("%.2f", 3.14159) == "3.14"
        assert locale.format_string("%8.3f", 3.14159) == "   3.142"
        assert locale.format_string("%-8s|", "ab") == "ab      |"

    def test_format_string_keeps_plain_digits_without_grouping(self):
        """C locale 没有千位分隔符,grouping=True 也不会插入分隔符。"""
        locale.setlocale(locale.LC_ALL, "C")
        assert locale.format_string("%d", 1234567) == "1234567"
        assert locale.format_string("%d", 1234567, grouping=True) == "1234567"

    def test_format_string_accepts_mapping_values(self):
        """format_string 接受字典作为取值来源,命名占位符被真实替换。"""
        assert locale.format_string("%(price)d units", {"price": 42}) == "42 units"
        assert locale.format_string("%(price).2f units", {"price": 3.14159}) == "3.14 units"

    def test_delocalize_and_localize_follow_c_locale_conventions(self):
        """C locale 的千位分隔符为空、小数点是 "."，两个方向的换算结果明确。"""
        locale.setlocale(locale.LC_ALL, "C")
        assert locale.delocalize("1234.56") == "1234.56"
        assert locale.delocalize("1,234.56") == "1,234.56"
        assert locale.localize("1234.5") == "1234.5"
        assert locale.atof("3.5") == 3.5
        with pytest.raises(ValueError, match="could not convert string to float"):
            locale.atof("1,234.56")


class TestLocaleCollation:
    """strxfrm / strcoll / currency 的真实行为。"""

    def test_strxfrm_builds_collation_key_preserving_order(self):
        """C locale 下 strxfrm 是恒等映射,排序键按字节序排列且可重复计算。"""
        locale.setlocale(locale.LC_ALL, "C")
        assert locale.strxfrm("Apple") == "Apple"
        assert locale.strxfrm("banana") == "banana"
        assert locale.strxfrm(locale.strxfrm("Apple")) == locale.strxfrm("Apple")
        ordered = sorted(["banana", "cherry", "Apple"], key=locale.strxfrm)
        assert ordered == ["Apple", "banana", "cherry"]

    def test_strcoll_orders_strings_by_collating_sequence(self):
        """strcoll 在 C locale 下按字节序排序。

        只断言符号:C 标准只保证返回负 / 零 / 正,具体数值由实现决定
        (glibc 在某些 locale 下返回 -4 而不是 -1)。断言精确值的话,换个
        环境就飘 —— 这条用例在流水线上红过。
        """
        locale.setlocale(locale.LC_ALL, "C")
        assert locale.strcoll("a", "b") < 0
        assert locale.strcoll("b", "a") > 0
        assert locale.strcoll("a", "a") == 0

    def test_currency_raises_in_c_locale(self):
        """C locale 无法给出货币格式,currency 抛 ValueError 并说明原因。"""
        locale.setlocale(locale.LC_ALL, "C")
        with pytest.raises(ValueError, match="Currency formatting is not possible"):
            locale.currency(1234.5)

    @requires_c_utf8
    @requires_codeset
    def test_nl_langinfo_codeset_reflects_ctype_locale(self):
        """nl_langinfo(CODESET) 跟随 LC_CTYPE:C.UTF-8 给 UTF-8,C locale 给 ASCII 家族。"""
        locale.setlocale(locale.LC_ALL, "C.UTF-8")
        assert locale.nl_langinfo(locale.CODESET) == "UTF-8"
        locale.setlocale(locale.LC_ALL, "C")
        assert locale.nl_langinfo(locale.CODESET) != "UTF-8"
        assert codecs.lookup(locale.nl_langinfo(locale.CODESET)).name == "ascii"


class TestLocaleAliasTable:
    """别名表与已弃用接口。"""

    def test_locale_alias_table_normalizes_known_names(self):
        """locale_alias 与 normalize 对已知名字给出确定的归一化结果。"""
        assert locale.locale_alias["en_us"] == "en_US.ISO8859-1"
        assert locale.locale_alias["c"] == "C"
        assert locale.normalize("en_US") == "en_US.ISO8859-1"
        assert locale.normalize("C.UTF-8") == "en_US.UTF-8"
        assert locale.normalize("POSIX") == "C"

    @pytest.mark.skipif(
        not HAS_GETDEFAULTLOCALE,
        reason="当前 Python 已移除 locale.getdefaultlocale(3.13 起删除)",
    )
    def test_getdefaultlocale_is_deprecated_and_unaffected_by_setlocale(self):
        """getdefaultlocale 触发 DeprecationWarning,且返回值不随 setlocale 改变。"""
        assert hasattr(locale, "getdefaultlocale")
        with pytest.warns(DeprecationWarning, match="setlocale"):
            before = locale.getdefaultlocale()
        locale.setlocale(locale.LC_ALL, "C")
        with pytest.warns(DeprecationWarning, match="setlocale"):
            after = locale.getdefaultlocale()
        assert before == after
        language, encoding = before
        assert language is None or re.fullmatch(r"[a-z]{2,3}(_[A-Z]{2})?", language)
        assert encoding is None or codecs.lookup(encoding).name in {"utf-8", "ascii"}
