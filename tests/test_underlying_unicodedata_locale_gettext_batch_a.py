# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""unicodedata 方向的底层真实行为测试:字符属性查询、Unicode 名称、规范化与东亚宽度。

覆盖模块:unicodedata(标准库,绑定 Unicode 14.0.0 字符数据库)。

真实测试项(共 18 个):
  1. lookup 按 Unicode 算法名反查码位,命中 "A"
  2. lookup 命中带附加符的复合名与连字名
  3. lookup 遇到未知名称抛 KeyError
  4. name 给出完整的 Unicode 算法名
  5. name 的 default 参数覆盖无名控制字符,无名时抛 ValueError
  6. category 区分 Lu/Ll/Lo/Nd/Zs/Cc/Po/No/Nl/Mn 等真实类别
  7. bidirectional 给出 L/R/EN/ON/WS/AL 等真实双向类别
  8. combining 给出真实规范组合等级
  9. decimal/digit/numeric 给出真实数值
 10. decimal/digit/numeric 对非数值字符抛 ValueError
 11. numeric 覆盖罗马数字与分数等非十进制数值
 12. east_asian_width 给出 Na/W/F/H/A 等真实宽度
 13. normalize 的 NFC 合成与 NFD 分解
 14. normalize 的 NFKC/NFKD 兼容分解
 15. normalize 对四种形式均满足幂等与收敛
 16. is_normalized 的判定与 normalize 结果一致
 17. decomposition 给出规范分解与兼容分解标记
 18. 主库版本与 ucd_3_2_0 旧版数据库各自报告真实 Unicode 版本

测试数据里的非 ASCII 字符一律写成码位转义,避免源码里预组合写法与分解写法
混在一起导致期望值含义漂移。
"""

import sys
import unicodedata

import pytest

# 各 Python 小版本绑定的 Unicode 字符数据库版本,用于核对 unicodedata.unidata_version。
UNICODE_VERSION_BY_PYTHON = {
    "3.11": "14.0.0",
    "3.12": "15.0.0",
    "3.13": "15.1.0",
    "3.14": "16.0.0",
}

# 测试用代表字符,全部使用码位转义保证唯一性。
E_ACUTE_PRECOMPOSED = "\u00e9"  # U+00E9
E_ACUTE_DECOMPOSED = "\u0065\u0301"  # U+0065 U+0301
COMBINING_ACUTE = "\u0301"  # U+0301
COMBINING_CEDILLA = "\u0327"  # U+0327
CJK_ZHONG = "\u4e2d"  # U+4E2D
CIRCLED_DIGIT_ONE = "\u2460"  # U+2460
ROMAN_NUMERAL_TWELVE = "\u216b"  # U+216B
VULGAR_HALF = "\u00bd"  # U+00BD
FULLWIDTH_ONE = "\uff11"  # U+FF11
FULLWIDTH_FIVE = "\uff15"  # U+FF15
FULLWIDTH_COMMA = "\uff0c"  # U+FF0C
FULLWIDTH_A = "\uff21"  # U+FF21
HALFWIDTH_KATAKANA_A = "\uff71"  # U+FF71
HIRAGANA_A = "\u3042"  # U+3042
LIGATURE_FI = "\ufb01"  # U+FB01
ARABIC_INDIC_FIVE = "\u0665"  # U+0665
ARABIC_ALEF = "\u0627"  # U+0627
HEBREW_ALEF = "\u05d0"  # U+05D0
HANGUL_GA = "\uac00"  # U+AC00
SUPERSCRIPT_TWO = "\u00b2"  # U+00B2
ANGSTROM = "\u00c5"  # U+00C5
LATIN_SMALL_A_DIAERESIS = "\u00e4"  # U+00E4
LATIN_CAPITAL_AE = "\u00c6"  # U+00C6
FRACTION_ONE_SLASH_TWO = "\u0031\u2044\u0032"  # U+0031 U+2044 U+0032


class TestUnicodedataLookupAndName:
    """lookup 与 name 的双向映射。"""

    def test_lookup_returns_latin_capital_a_for_exact_name(self):
        """lookup("LATIN CAPITAL LETTER A") 真实返回 "A",码位为 0x41。"""
        found = unicodedata.lookup("LATIN CAPITAL LETTER A")
        assert found == "A"
        assert ord(found) == 0x41

    def test_lookup_resolves_diacritic_and_ligature_names(self):
        """lookup 对带附加符与连字的名字分别返回 U+00E4 与 U+00C6。"""
        assert unicodedata.lookup("LATIN SMALL LETTER A WITH DIAERESIS") == LATIN_SMALL_A_DIAERESIS
        assert ord(unicodedata.lookup("LATIN SMALL LETTER A WITH DIAERESIS")) == 0xE4
        assert unicodedata.lookup("LATIN CAPITAL LETTER AE") == LATIN_CAPITAL_AE
        assert ord(unicodedata.lookup("LATIN CAPITAL LETTER AE")) == 0xC6

    def test_lookup_raises_keyerror_for_unknown_name(self):
        """lookup 遇到库里不存在的名称抛 KeyError,而不是返回 None。"""
        with pytest.raises(KeyError):
            unicodedata.lookup("LATIN CAPITAL LETTER NOT A REAL GLYPH")

    def test_name_returns_full_unicode_algorithm_name(self):
        """name 给出完整算法名,包括带附加符字母、汉字与带圈数字。"""
        assert unicodedata.name("A") == "LATIN CAPITAL LETTER A"
        assert unicodedata.name(E_ACUTE_PRECOMPOSED) == "LATIN SMALL LETTER E WITH ACUTE"
        assert unicodedata.name(CJK_ZHONG) == "CJK UNIFIED IDEOGRAPH-4E2D"
        assert unicodedata.name(CIRCLED_DIGIT_ONE) == "CIRCLED DIGIT ONE"

    def test_name_default_argument_covers_unnamed_control_char(self):
        """无名控制字符用 default 参数接住,不给 default 时抛 ValueError。"""
        assert unicodedata.name("\x00", "<unnamed>") == "<unnamed>"
        assert unicodedata.name("\x00", "") == ""
        with pytest.raises(ValueError, match="no such name"):
            unicodedata.name("\x00")


class TestUnicodedataCharacterAttributes:
    """category / bidirectional / combining / decimal / numeric / east_asian_width。"""

    def test_category_distinguishes_real_unicode_classes(self):
        """category 对每类代表字符返回真实的两字母类别码。"""
        expected = {
            "A": "Lu",
            "z": "Ll",
            CJK_ZHONG: "Lo",
            "0": "Nd",
            "9": "Nd",
            " ": "Zs",
            "\t": "Cc",
            "!": "Po",
            CIRCLED_DIGIT_ONE: "No",
            ROMAN_NUMERAL_TWELVE: "Nl",
            E_ACUTE_PRECOMPOSED: "Ll",
            COMBINING_ACUTE: "Mn",
            HANGUL_GA: "Lo",
        }
        for char, category in expected.items():
            assert unicodedata.category(char) == category, f"字符 {char!r} 的类别不符"

    def test_bidirectional_returns_real_bidi_classes(self):
        """bidirectional 给出 L/R/EN/ON/WS/AL 六种真实双向类别。"""
        assert unicodedata.bidirectional("A") == "L"
        assert unicodedata.bidirectional(HEBREW_ALEF) == "R"
        assert unicodedata.bidirectional("1") == "EN"
        assert unicodedata.bidirectional("(") == "ON"
        assert unicodedata.bidirectional(" ") == "WS"
        assert unicodedata.bidirectional(ARABIC_ALEF) == "AL"

    def test_combining_returns_real_canonical_combining_class(self):
        """combining 对组合记号给出真实等级,普通字母与汉字为 0。"""
        assert unicodedata.combining(COMBINING_ACUTE) == 230
        assert unicodedata.combining(COMBINING_CEDILLA) == 202
        assert unicodedata.combining("A") == 0
        assert unicodedata.combining(CJK_ZHONG) == 0

    def test_decimal_digit_and_numeric_return_real_values(self):
        """decimal/digit/numeric 对可数字符给出真实数值。"""
        assert unicodedata.decimal("1") == 1
        assert unicodedata.decimal("9") == 9
        assert unicodedata.digit("7") == 7
        assert unicodedata.digit(ARABIC_INDIC_FIVE) == 5
        assert unicodedata.decimal(ARABIC_INDIC_FIVE) == 5
        assert unicodedata.decimal(FULLWIDTH_ONE) == 1
        assert unicodedata.digit(FULLWIDTH_FIVE) == 5
        assert unicodedata.numeric(CIRCLED_DIGIT_ONE) == 1.0
        assert unicodedata.numeric(VULGAR_HALF) == 0.5

    def test_decimal_digit_numeric_raise_valueerror_on_non_numeric(self):
        """decimal/digit/numeric 对字母与分数抛 ValueError,不做静默返回。"""
        with pytest.raises(ValueError, match="not a decimal"):
            unicodedata.decimal("A")
        with pytest.raises(ValueError, match="not a digit"):
            unicodedata.digit("A")
        with pytest.raises(ValueError, match="not a numeric character"):
            unicodedata.numeric("A")
        with pytest.raises(ValueError, match="not a decimal"):
            unicodedata.decimal(VULGAR_HALF)

    def test_numeric_covers_roman_numeral_and_fraction(self):
        """numeric 对罗马数字、分数与上标数字给出真实数值,类别码分别落在 Nl 与 No。"""
        assert unicodedata.numeric(ROMAN_NUMERAL_TWELVE) == 12.0
        assert unicodedata.category(ROMAN_NUMERAL_TWELVE) == "Nl"
        assert unicodedata.numeric(VULGAR_HALF) == 0.5
        assert unicodedata.category(VULGAR_HALF) == "No"
        assert unicodedata.numeric(SUPERSCRIPT_TWO) == 2.0
        assert unicodedata.category(SUPERSCRIPT_TWO) == "No"

    def test_east_asian_width_returns_real_width_values(self):
        """east_asian_width 给出 Na/W/F/H/A 五种真实宽度取值。"""
        assert unicodedata.east_asian_width("A") == "Na"
        assert unicodedata.east_asian_width(CJK_ZHONG) == "W"
        assert unicodedata.east_asian_width(HIRAGANA_A) == "W"
        assert unicodedata.east_asian_width(FULLWIDTH_ONE) == "F"
        assert unicodedata.east_asian_width(FULLWIDTH_COMMA) == "F"
        assert unicodedata.east_asian_width(HALFWIDTH_KATAKANA_A) == "H"
        assert unicodedata.east_asian_width(CIRCLED_DIGIT_ONE) == "A"


class TestUnicodedataNormalization:
    """normalize 的四种形式与 is_normalized。"""

    def test_normalize_nfc_composes_and_nfd_decomposes(self):
        """NFC 把 e+组合尖音合成 U+00E9,NFD 把 U+00E9 拆回两个码位。"""
        assert unicodedata.normalize("NFC", E_ACUTE_DECOMPOSED) == E_ACUTE_PRECOMPOSED
        assert len(unicodedata.normalize("NFC", E_ACUTE_DECOMPOSED)) == 1
        assert unicodedata.normalize("NFD", E_ACUTE_PRECOMPOSED) == E_ACUTE_DECOMPOSED
        assert len(unicodedata.normalize("NFD", E_ACUTE_PRECOMPOSED)) == 2
        assert unicodedata.normalize("NFD", E_ACUTE_PRECOMPOSED)[1] == COMBINING_ACUTE

    def test_normalize_nfkc_nfkd_apply_compatibility_mapping(self):
        """NFKC/NFKD 做兼容分解:连字变 fi,带圈数字变 1,全角字母变 A。"""
        assert unicodedata.normalize("NFKC", LIGATURE_FI) == "fi"
        assert unicodedata.normalize("NFKD", LIGATURE_FI) == "fi"
        assert unicodedata.normalize("NFKC", CIRCLED_DIGIT_ONE) == "1"
        assert unicodedata.normalize("NFKD", CIRCLED_DIGIT_ONE) == "1"
        assert unicodedata.normalize("NFKC", FULLWIDTH_A) == "A"
        assert unicodedata.normalize("NFKC", VULGAR_HALF) == FRACTION_ONE_SLASH_TWO

    def test_normalize_is_idempotent_and_convergent_for_all_forms(self):
        """四种规范化形式都满足幂等,且 NFC 作用于 NFD 结果后收敛到同一形态。"""
        samples = [
            E_ACUTE_PRECOMPOSED,
            E_ACUTE_DECOMPOSED,
            LIGATURE_FI,
            CIRCLED_DIGIT_ONE,
            ROMAN_NUMERAL_TWELVE,
            CJK_ZHONG,
            HANGUL_GA,
        ]
        for form in ("NFC", "NFD", "NFKC", "NFKD"):
            for sample in samples:
                once = unicodedata.normalize(form, sample)
                assert unicodedata.normalize(form, once) == once, f"{form} 形式不幂等"
                assert unicodedata.normalize("NFC", unicodedata.normalize("NFD", sample)) == (
                    unicodedata.normalize("NFC", sample)
                )

    def test_is_normalized_agrees_with_normalize_result(self):
        """is_normalized 的布尔结果与 normalize 是否改变原串完全一致。"""
        assert unicodedata.is_normalized("NFC", E_ACUTE_PRECOMPOSED) is True
        assert unicodedata.is_normalized("NFD", E_ACUTE_PRECOMPOSED) is False
        assert unicodedata.is_normalized("NFD", E_ACUTE_DECOMPOSED) is True
        assert unicodedata.is_normalized("NFKC", LIGATURE_FI) is False
        assert unicodedata.is_normalized("NFKC", "fi") is True
        assert unicodedata.is_normalized("NFKD", VULGAR_HALF) is False
        for form in ("NFC", "NFD", "NFKC", "NFKD"):
            for sample in (E_ACUTE_PRECOMPOSED, LIGATURE_FI, CIRCLED_DIGIT_ONE, CJK_ZHONG):
                assert unicodedata.is_normalized(form, sample) == (
                    unicodedata.normalize(form, sample) == sample
                )

    def test_decomposition_reports_canonical_and_compatibility_sequences(self):
        """decomposition 给出规范分解序列,兼容分解带 <compat> 前缀,汉字无分解。"""
        assert unicodedata.decomposition(E_ACUTE_PRECOMPOSED) == "0065 0301"
        assert unicodedata.decomposition(ANGSTROM) == "0041 030A"
        assert unicodedata.decomposition(LIGATURE_FI) == "<compat> 0066 0069"
        assert unicodedata.decomposition(VULGAR_HALF) == "<fraction> 0031 2044 0032"
        assert unicodedata.decomposition(CJK_ZHONG) == ""


class TestUnicodedataVersionedDatabase:
    """字符数据库版本与旧版数据库入口。"""

    def test_unicode_database_versions_match_running_interpreter(self):
        """主库版本等于解释器绑定的 Unicode 版本,ucd_3_2_0 是独立的 3.2.0 数据库。"""
        assert unicodedata.ucd_3_2_0.unidata_version == "3.2.0"
        assert unicodedata.ucd_3_2_0.category("A") == "Lu"
        assert unicodedata.ucd_3_2_0.name("A") == "LATIN CAPITAL LETTER A"
        assert unicodedata.ucd_3_2_0.lookup("LATIN CAPITAL LETTER A") == "A"
        assert unicodedata.ucd_3_2_0.unidata_version != unicodedata.unidata_version

        key = f"{sys.version_info.major}.{sys.version_info.minor}"
        expected = UNICODE_VERSION_BY_PYTHON.get(key)
        if expected is None:
            pytest.skip(f"Python {key} 的 Unicode 数据库版本未登记,跳过版本核对")
        assert unicodedata.unidata_version == expected
