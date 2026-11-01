# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""真 regex"""
import re
import time
import pytest

def test_regex_simple_match():
    m = re.match(r"hello", "hello world")
    assert m.group(0) == "hello"
    s = re.search(r"world", "hello world")
    assert s.group(0) == "world"
    assert re.findall(r"\d+", "a1 b22 c333") == ["1", "22", "333"]

def test_regex_groups_named():
    m = re.match(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})", "2026-10-13")
    assert m.group("year") == "2026"
    assert m.groupdict() == {"year": "2026", "month": "10", "day": "13"}

def test_regex_backreference():
    p = re.compile(r"\b(\w+)\s+\1\b")
    assert p.search("hello hello world") is not None
    assert p.search("hello world") is None
    p2 = re.compile(r"<(\w+)>.*?</\1>")
    assert p2.search("<b>bold</b>") is not None
    assert p2.search("<b>bold</i>") is None

def test_regex_lookahead_lookbehind():
    assert re.search(r"\d+(?=%)", "50% off").group(0) == "50"
    m = re.search(r"\d+(?!%)", "50% off 100")
    assert m.group(0) in ("5", "100")
    assert re.search(r"(?<=\$)\d+", "$100") is not None
    assert re.search(r"(?<=\$)\d+", "100") is None

def test_regex_flags_real():
    assert re.match(r"hello", "HELLO", re.IGNORECASE) is not None
    p = re.compile(r"^line", re.MULTILINE)
    assert len(p.findall("line 1\nline 2\nline 3")) == 3
    p2 = re.compile(r"start.*end", re.DOTALL)
    assert p2.search("start\nmiddle\nend") is not None
    p3 = re.compile(r"start.*end")
    assert p3.search("start\nmiddle\nend") is None

def test_regex_sub_subn_split():
    assert re.sub(r"\d+", "X", "a1 b22 c333") == "aX bX cX"
    new, n = re.subn(r"\d+", "X", "a1 b22 c333")
    assert n == 3
    assert re.sub(r"\d+", lambda m: str(int(m.group(0)) * 2), "a1 b2 c3") == "a2 b4 c6"
    assert re.split(r"\s+", "hello  world\t\n  foo") == ["hello", "world", "foo"]

def test_regex_anchors_word_boundary():
    p = re.compile(r"\bcat\b")
    assert p.search("cat") is not None
    assert p.search("category") is None
    p2 = re.compile(r"\Bcat\B")
    assert p2.search("a1cat1b") is not None
    assert p2.search("cat") is None

def test_regex_greedy_nongreedy():
    text = "<b>bold</b> and <i>italic</i>"
    p1 = re.compile(r"<.*>")
    assert p1.search(text).group(0) == "<b>bold</b> and <i>italic</i>"
    p2 = re.compile(r"<.*?>")
    assert p2.findall(text) == ["<b>", "</b>", "<i>", "</i>"]

def test_regex_unicode():
    p = re.compile(r"\w+", re.UNICODE)
    assert p.findall("中文 hello 123") == ["中文", "hello", "123"]

def test_regex_performance_real():
    text = "\n".join([f"Call 555-{i:04d}" for i in range(1000)])
    p = re.compile(r"555-\d{4}")
    start = time.time()
    matches = p.findall(text)
    elapsed = time.time() - start
    assert len(matches) == 1000
    assert elapsed < 1.0

def test_regex_compile_cache():
    re.compile(r"\d+")
    re.compile(r"\d+", re.IGNORECASE)
    re.purge()
    p = re.compile(r"\d+")
    assert p.pattern == r"\d+"

def test_regex_error_invalid():
    with pytest.raises(re.error):
        re.compile(r"(unclosed")

def test_regex_fullmatch():
    assert re.fullmatch(r"\d+", "12345") is not None
    assert re.fullmatch(r"\d+", "123a") is None
