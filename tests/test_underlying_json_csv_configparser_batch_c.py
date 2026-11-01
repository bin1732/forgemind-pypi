# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""configparser 模块的真实行为验证

覆盖模块:configparser(标准库)

真实测试项(共 18 个):
   1. add_section/set/get 之后选项能被原样读回
   2. sections/options/items 返回的确切列表与键值对
   3. getint 与 getfloat 把字符串转成确切数值
   4. getboolean 认得 yes/no/true/false/on/off/1/0 八种写法
   5. getboolean 遇到无法识别的取值时抛 ValueError,消息确切
   6. getint 遇到非整数字符串时抛 ValueError,消息确切
   7. BasicInterpolation 把 %(name)s 展开成被引用选项的值
   8. 插值引用的选项不存在时抛 InterpolationMissingOptionError,消息确切
   9. interpolation=None 时 %(name)s 原样保留,不展开
  10. DEFAULT 段的默认值被其它段继承,取值顺序与来源都确切
  11. read 读真实文件后返回成功解析的文件名列表,缺失文件返回空列表
  12. read_string 解析出的段名与选项值确切
  13. read_dict 按给定字典建出段与选项
  14. write 写出的文本逐字符确切
  15. remove_section / remove_option 的返回值与缺失段异常都确切
  16. 映射协议 parser["段"]["选项"] 能读能写,缺段抛 KeyError
  17. optionxform 设为 str 后选项名大小写被保留
  18. allow_unnamed_section 让首个段之前的键值进入无名段(3.13+)

3.13 才引入的无名段特性用 hasattr 判定并配合 skipif 跳过。
"""

import configparser
import io
import re
from pathlib import Path

import pytest

# configparser.UNNAMED_SECTION 与 allow_unnamed_section 自 Python 3.13 起提供。
_HAS_UNNAMED_SECTION = hasattr(configparser, "UNNAMED_SECTION")


def test_configparser_add_section_and_set_option_round_trip() -> None:
    """新建段并设置选项后,get/has_section/has_option 给出确切结果。"""
    parser = configparser.ConfigParser()
    parser.add_section("alpha")
    parser.set("alpha", "key", "value")
    assert parser.get("alpha", "key") == "value"
    assert parser.has_section("alpha") is True
    assert parser.has_option("alpha", "key") is True
    assert parser.has_section("beta") is False
    assert parser.has_option("alpha", "missing") is False


def test_configparser_sections_options_and_items_are_exact() -> None:
    """sections 列出段名,options 列出选项名,items 给出键值对。"""
    parser = configparser.ConfigParser()
    parser.add_section("alpha")
    parser.set("alpha", "key", "value")
    parser.set("alpha", "num", "42")
    parser.add_section("beta")
    assert parser.sections() == ["alpha", "beta"]
    assert parser.options("alpha") == ["key", "num"]
    assert parser.items("alpha") == [("key", "value"), ("num", "42")]


def test_configparser_getint_and_getfloat_convert_values() -> None:
    """getint 得到整数,getfloat 得到浮点数,取值都确切。"""
    parser = configparser.ConfigParser()
    parser.add_section("s")
    parser.set("s", "count", "-7")
    parser.set("s", "ratio", "2.5")
    assert parser.getint("s", "count") == -7
    assert parser.getfloat("s", "ratio") == 2.5
    assert parser.get("s", "count") == "-7"


def test_configparser_getboolean_accepts_eight_spellings() -> None:
    """getboolean 对 1/yes/true/on 与 0/no/false/off 的各种大小写都给出确切布尔值。"""
    parser = configparser.ConfigParser()
    parser.add_section("s")
    for word in ("1", "yes", "true", "on", "YES", "True", "ON"):
        parser.set("s", word, word)
    for word in ("0", "no", "false", "off", "NO", "False", "OFF"):
        parser.set("s", word, word)
    for word in ("1", "yes", "true", "on", "YES", "True", "ON"):
        assert parser.getboolean("s", word) is True
    for word in ("0", "no", "false", "off", "NO", "False", "OFF"):
        assert parser.getboolean("s", word) is False


def test_configparser_getboolean_rejects_unknown_value() -> None:
    """无法识别的取值让 getboolean 抛 ValueError,消息里带出原值。"""
    parser = configparser.ConfigParser()
    parser.add_section("s")
    parser.set("s", "flag", "maybe")
    with pytest.raises(ValueError, match=re.escape("Not a boolean: maybe")):
        parser.getboolean("s", "flag")


def test_configparser_getint_rejects_non_integer_value() -> None:
    """非整数字符串让 getint 抛 ValueError,消息里带出原值。"""
    parser = configparser.ConfigParser()
    parser.add_section("s")
    parser.set("s", "count", "2.5")
    with pytest.raises(
        ValueError,
        match=re.escape("invalid literal for int() with base 10: '2.5'"),
    ):
        parser.getint("s", "count")


def test_configparser_basic_interpolation_expands_placeholder() -> None:
    """%(name)s 展开成被引用选项的值,raw=True 时返回未展开原文。"""
    parser = configparser.ConfigParser()
    parser.add_section("s")
    parser.set("s", "host", "localhost")
    parser.set("s", "url", "http://%(host)s:8080")
    assert parser.get("s", "url") == "http://localhost:8080"
    assert parser.get("s", "url", raw=True) == "http://%(host)s:8080"


def test_configparser_interpolation_missing_option_reports_exact_message() -> None:
    """插值引用的选项不存在时抛 InterpolationMissingOptionError,消息确切。"""
    parser = configparser.ConfigParser()
    parser.add_section("s")
    parser.set("s", "url", "http://%(missing)s")
    with pytest.raises(configparser.InterpolationMissingOptionError) as excinfo:
        parser.get("s", "url")
    assert str(excinfo.value) == (
        "Bad value substitution: option 'url' in section 's' contains an "
        "interpolation key 'missing' which is not a valid option name. "
        "Raw value: 'http://%(missing)s'"
    )


def test_configparser_interpolation_none_keeps_literal_text() -> None:
    """interpolation=None 时 %(name)s 原样返回,不发生展开。"""
    parser = configparser.ConfigParser(interpolation=None)
    parser.add_section("s")
    parser.set("s", "host", "localhost")
    parser.set("s", "url", "http://%(host)s:8080")
    assert parser.get("s", "url") == "http://%(host)s:8080"


def test_configparser_defaults_are_inherited_by_sections() -> None:
    """DEFAULT 段里的默认值被其它段继承,取值来源与选项列表都确切。"""
    parser = configparser.ConfigParser({"shared": "sval"})
    parser.add_section("s1")
    parser.set("s1", "own", "o")
    assert parser.defaults() == {"shared": "sval"}
    assert parser.options("s1") == ["own", "shared"]
    assert parser.items("s1") == [("shared", "sval"), ("own", "o")]
    assert parser.get("s1", "shared") == "sval"
    assert parser.has_option("s1", "shared") is True


def test_configparser_read_parses_real_file_and_lists_paths(tmp_path: Path) -> None:
    """read 读真实文件后返回成功解析的文件名列表,读不存在的文件返回空列表。"""
    target = tmp_path / "settings.ini"
    target.write_text("[main]\nhost = localhost\nport = 8080\n", encoding="utf-8")
    parser = configparser.ConfigParser()
    assert parser.read(str(target)) == [str(target)]
    assert parser.sections() == ["main"]
    assert parser.get("main", "host") == "localhost"
    assert parser.getint("main", "port") == 8080
    assert parser.read(str(tmp_path / "absent.ini")) == []


def test_configparser_read_string_parses_sections_and_values() -> None:
    """read_string 解析出的段名顺序与各选项取值都确切。"""
    parser = configparser.ConfigParser()
    parser.read_string("[s1]\na = 1\nb = two\n[s2]\nc = 3\n")
    assert parser.sections() == ["s1", "s2"]
    assert parser.get("s1", "a") == "1"
    assert parser.get("s1", "b") == "two"
    assert parser.get("s2", "c") == "3"


def test_configparser_read_dict_populates_sections() -> None:
    """read_dict 按给定字典建出段与选项,取值与段顺序都确切。"""
    parser = configparser.ConfigParser()
    parser.read_dict({"sec": {"opt": "1", "other": "2"}})
    assert parser.sections() == ["sec"]
    assert parser.options("sec") == ["opt", "other"]
    assert parser.get("sec", "other") == "2"


def test_configparser_write_emits_exact_text() -> None:
    """write 写出的段名与键值文本逐字符确切。"""
    parser = configparser.ConfigParser()
    parser.add_section("a")
    parser.set("a", "k", "v")
    parser.add_section("b")
    parser.set("b", "k2", "v2")
    buffer = io.StringIO()
    parser.write(buffer)
    assert buffer.getvalue() == "[a]\nk = v\n\n[b]\nk2 = v2\n\n"


def test_configparser_remove_section_and_option_return_flags() -> None:
    """remove_option 与 remove_section 对存在的项返回 True,重复删除返回 False。"""
    parser = configparser.ConfigParser()
    parser.add_section("a")
    parser.set("a", "k", "v")
    assert parser.remove_option("a", "k") is True
    assert parser.remove_option("a", "k") is False
    assert parser.remove_section("a") is True
    assert parser.remove_section("a") is False
    with pytest.raises(configparser.NoSectionError, match=re.escape("No section: 'a'")):
        parser.get("a", "k")


def test_configparser_mapping_protocol_reads_and_writes_options() -> None:
    """映射协议既能读选项也能写选项,访问不存在的段抛 KeyError。"""
    parser = configparser.ConfigParser()
    parser["s"] = {"k": "v"}
    parser["s"]["n"] = "w"
    assert parser["s"]["k"] == "v"
    assert parser["s"]["n"] == "w"
    assert parser.options("s") == ["k", "n"]
    with pytest.raises(KeyError) as excinfo:
        parser["missing"]
    assert excinfo.value.args == ("missing",)


def test_configparser_optionxform_preserves_option_name_case() -> None:
    """optionxform 设为 str 后,选项名的大小写被原样保留。"""
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.add_section("s")
    parser.set("s", "MixedCase", "1")
    assert parser.options("s") == ["MixedCase"]
    assert parser.get("s", "MixedCase") == "1"


@pytest.mark.skipif(
    not _HAS_UNNAMED_SECTION,
    reason="configparser.UNNAMED_SECTION 与 allow_unnamed_section 需要 Python 3.13+",
)
def test_configparser_unnamed_section_collects_leading_keys() -> None:
    """allow_unnamed_section=True 时,首个段之前的键值进入无名段。"""
    parser = configparser.ConfigParser(allow_unnamed_section=True)
    parser.read_string("first: one\nsecond: two\n\n[MySection]\nthird: three\n")
    assert parser.get(configparser.UNNAMED_SECTION, "first") == "one"
    assert parser.get(configparser.UNNAMED_SECTION, "second") == "two"
    assert parser.get("MySection", "third") == "three"
