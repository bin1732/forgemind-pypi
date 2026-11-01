# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""csv 模块的真实行为验证

覆盖模块:csv(标准库)

真实测试项(共 18 个):
   1. reader 按 excel 方言把文本解析成确切的多行列表
   2. reader 接受 dialect 名称与 delimiter 参数两种写法
   3. reader(skipinitialspace=True) 去掉字段前导空格
   4. reader(quoting=QUOTE_NONE, escapechar=...) 时逗号留在字段内
   5. reader(strict=True) 对未闭合引号报出确切错误文本
   6. DictReader 暴露表头字段名,并把每行解析成确切字典
   7. DictReader(restval=...) 给缺列的行补上确切占位值
   8. DictReader(restkey=...) 把多出的列收进确切键名
   9. DictWriter 先写表头再写数据行,输出文本确切
  10. DictWriter 的 extrasaction 两种策略给出确切结果
  11. DictWriter(restval=...) 给缺键的行补上确切占位值
  12. writer 默认行结束符是 \\r\\n,指定 lineterminator 后变成 \\n
  13. writer(quoting=QUOTE_ALL) 给每个字段加引号
  14. writer(quoting=QUOTE_NONNUMERIC) 只给非数字字段加引号
  15. writer 对字段内嵌的引号与分隔符给出确切转义结果
  16. Sniffer 探测出确切的分隔符、引号字符与表头判定
  17. DictWriter 写出、DictReader 读回后每行取值完全一致
  18. csv.QUOTE_NOTNULL / csv.QUOTE_STRINGS 两个新引号策略(3.12+)

写文件时统一用 newline="" 或 StringIO,断言里的行结束符不随平台变化。
3.12 才引入的引号常量用 hasattr 判定并配合 skipif 跳过。
"""

import csv
import io
import re

import pytest

# csv.QUOTE_NOTNULL 与 csv.QUOTE_STRINGS 自 Python 3.12 起提供。
_HAS_NEW_QUOTE_FLAGS = hasattr(csv, "QUOTE_NOTNULL") and hasattr(csv, "QUOTE_STRINGS")


def test_csv_reader_parses_default_dialect_rows() -> None:
    """默认 excel 方言把两行三列文本解析成确切的两个列表。"""
    rows = list(csv.reader(io.StringIO("a,b,c\n1,2,3\n")))
    assert rows == [["a", "b", "c"], ["1", "2", "3"]]


def test_csv_reader_accepts_dialect_name_and_delimiter_argument() -> None:
    """dialect="excel-tab" 与 delimiter=";" 两种写法都按指定分隔符切列。"""
    tabbed = list(csv.reader(io.StringIO("a\tb\n1\t2\n"), dialect="excel-tab"))
    assert tabbed == [["a", "b"], ["1", "2"]]
    semicolons = list(csv.reader(io.StringIO("a;b\n1;2\n"), delimiter=";"))
    assert semicolons == [["a", "b"], ["1", "2"]]
    assert csv.get_dialect("excel-tab").delimiter == "\t"


def test_csv_reader_skipinitialspace_strips_leading_spaces() -> None:
    """skipinitialspace=True 时字段前导空格被去掉,尾部空格保留。"""
    rows = list(csv.reader(io.StringIO("a, b ,  c\n"), skipinitialspace=True))
    assert rows == [["a", "b ", "c"]]
    plain = list(csv.reader(io.StringIO("a, b ,  c\n")))
    assert plain == [["a", " b ", "  c"]]


def test_csv_reader_quote_none_keeps_delimiters_inside_field() -> None:
    """QUOTE_NONE 配合 escapechar 时,被转义的逗号留在同一个字段里。"""
    rows = list(
        csv.reader(
            io.StringIO('a,b\n"x,1,2\n'),
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
        )
    )
    assert rows == [["a", "b"], ['"x', "1", "2"]]


def test_csv_reader_strict_reports_unbalanced_quote() -> None:
    """strict=True 时未闭合的引号让 reader 抛出 csv.Error,文本确切。"""
    with pytest.raises(csv.Error, match=re.escape("',' expected after '\"'")):
        list(csv.reader(io.StringIO('a,"b"c\n'), strict=True))


def test_csv_dictreader_exposes_fieldnames_and_row_dicts() -> None:
    """DictReader 把首行当表头,fieldnames 与逐行字典都确切。"""
    reader = csv.DictReader(io.StringIO("a,b\n1,2\n3,4\n"))
    assert reader.fieldnames == ["a", "b"]
    assert list(reader) == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]


def test_csv_dictreader_restval_fills_missing_column() -> None:
    """缺列的行由 restval 补齐,补上的值与其它行一样是字符串。"""
    reader = csv.DictReader(io.StringIO("a,b\n1\n"), restval="NA")
    assert list(reader) == [{"a": "1", "b": "NA"}]


def test_csv_dictreader_restkey_collects_extra_column() -> None:
    """多出的列被收进 restkey 指定的键,值是列表。"""
    reader = csv.DictReader(io.StringIO("a,b\n1,2,3\n"), restkey="extra")
    assert list(reader) == [{"a": "1", "b": "2", "extra": ["3"]}]


def test_csv_dictwriter_writes_header_then_rows() -> None:
    """DictWriter 先写表头再写数据行,输出的文本逐字符确切。"""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["a", "b"], lineterminator="\n")
    writer.writeheader()
    writer.writerow({"a": 1, "b": 2})
    assert buffer.getvalue() == "a,b\n1,2\n"


def test_csv_dictwriter_extrasaction_policies_handle_unknown_key() -> None:
    """extrasaction="raise" 报出多余键,extrasaction="ignore" 把它丢弃。"""
    with pytest.raises(
        ValueError,
        match=re.escape("dict contains fields not in fieldnames: 'b'"),
    ):
        csv.DictWriter(io.StringIO(), fieldnames=["a"]).writerow({"a": 1, "b": 2})

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["a"],
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writerow({"a": 1, "b": 2})
    assert buffer.getvalue() == "1\n"


def test_csv_dictwriter_restval_writes_placeholder_for_missing_key() -> None:
    """缺键的行由 restval 补齐,写出的文本里占位值位置确切。"""
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["a", "b"],
        restval="NA",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerow({"a": 1})
    assert buffer.getvalue() == "a,b\n1,NA\n"


def test_csv_writer_default_terminator_is_crlf() -> None:
    """默认行结束符是 \\r\\n,显式指定 lineterminator 后变成 \\n。"""
    default_buffer = io.StringIO()
    csv.writer(default_buffer).writerow(["a", "b"])
    assert default_buffer.getvalue() == "a,b\r\n"

    unix_buffer = io.StringIO()
    csv.writer(unix_buffer, lineterminator="\n").writerow(["a", "b"])
    assert unix_buffer.getvalue() == "a,b\n"


def test_csv_writer_quote_all_wraps_every_field() -> None:
    """QUOTE_ALL 让每个字段都被引号包住,数字字段也一样。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(["a", 1, None])
    assert buffer.getvalue() == '"a","1",""\n'


def test_csv_writer_quote_nonnumeric_keeps_numeric_fields_unquoted() -> None:
    """QUOTE_NONNUMERIC 只给非数字字段加引号,数字字段保持裸写。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n")
    writer.writerow(["a", 1, 2.5])
    assert buffer.getvalue() == '"a",1,2.5\n'


def test_csv_writer_escapes_embedded_quotechar_and_delimiter() -> None:
    """字段里的引号被写成两个引号,分隔符被引号整体包住。"""
    buffer = io.StringIO()
    csv.writer(buffer).writerow(["x,y", 'he said "hi"'])
    assert buffer.getvalue() == '"x,y","he said ""hi"""\r\n'


def test_csv_sniffer_detects_delimiter_quotechar_and_header() -> None:
    """Sniffer 探测出分号分隔符与引号字符,还能判定首行是不是表头。"""
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff("a;b;c\n1;2;3\n4;5;6\n")
    assert dialect.delimiter == ";"
    assert dialect.quotechar == '"'
    assert sniffer.sniff("a\tb\tc\n1\t2\t3\n4\t5\t6\n").delimiter == "\t"
    assert sniffer.has_header("name,age\nalice,30\nbob,25\n") is True
    assert sniffer.has_header("1,2\n3,4\n") is False


def test_csv_dictwriter_dictreader_round_trip_preserves_values() -> None:
    """DictWriter 写出的文本交给 DictReader 读回,每行取值与原始行一致。"""
    rows = [
        {"symbol": "600519.SH", "close": "1688.50"},
        {"symbol": "000001.SZ", "close": "12.34"},
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["symbol", "close"], lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    assert buffer.getvalue() == "symbol,close\n600519.SH,1688.50\n000001.SZ,12.34\n"
    assert list(csv.DictReader(io.StringIO(buffer.getvalue()))) == rows


@pytest.mark.skipif(
    not _HAS_NEW_QUOTE_FLAGS,
    reason="csv.QUOTE_NOTNULL 与 csv.QUOTE_STRINGS 需要 Python 3.12+",
)
def test_csv_quote_notnull_and_quote_strings_policies() -> None:
    """QUOTE_STRINGS 只给字符串加引号,QUOTE_NOTNULL 只跳过 None 字段。"""
    strings_buffer = io.StringIO()
    writer = csv.writer(strings_buffer, quoting=csv.QUOTE_STRINGS, lineterminator="\n")
    writer.writerow(["text", 7, None])
    assert strings_buffer.getvalue() == '"text",7,\n'

    notnull_buffer = io.StringIO()
    writer = csv.writer(notnull_buffer, quoting=csv.QUOTE_NOTNULL, lineterminator="\n")
    writer.writerow(["text", 7, None])
    assert notnull_buffer.getvalue() == '"text","7",\n'
