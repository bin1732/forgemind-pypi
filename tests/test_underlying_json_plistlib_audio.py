# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 json 进阶 (encoder/decoder options) + 真 plistlib (xml + binary) + 真 wave (WAV 真写读) + 真 struct 嵌套真音频 + 真 token 真 flow。
全 stdlib, 零模拟。
"""
import json
import plistlib
import wave
import struct
import os
import tempfile
import pytest


# ======================== json ========================
def test_json_roundtrip_complex():
    """真 json 真 round-trip 复杂结构"""
    data = {
        "name": "Alice",
        "age": 30,
        "tags": ["python", "json", "data"],
        "nested": {"a": [1, 2, 3], "b": "hello"},
        "special": None,
    }
    s = json.dumps(data, ensure_ascii=False, indent=2)
    parsed = json.loads(s)
    assert parsed == data


def test_json_ensure_ascii_false():
    """真 ensure_ascii=False 真输出中"""
    data = {"name": "中文字符"}
    s = json.dumps(data, ensure_ascii=False)
    # 中文 raw UTF-8
    assert "中文字符" in s
    # 非 ensure_ascii 包含 \u 转义
    s_ascii = json.dumps(data, ensure_ascii=True)
    assert "\\u" in s_ascii


def test_json_custom_encoder():
    """真自定义 encoder"""
    class Custom:
        def __init__(self, x):
            self.x = x

    class MyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Custom):
                return {"type": "custom", "x": obj.x}
            return super().default(obj)

    data = {"obj": Custom(42)}
    s = json.dumps(data, cls=MyEncoder)
    parsed = json.loads(s)
    assert parsed == {"obj": {"type": "custom", "x": 42}}


def test_json_sort_keys():
    """真 sort_keys"""
    data = {"b": 1, "a": 2, "c": 3}
    s = json.dumps(data, sort_keys=True)
    # a 在 b 前
    assert s.index('"a"') < s.index('"b"') < s.index('"c"')


def test_json_object_pairs_hook():
    """真 object_pairs_hook 真转 OrderedDict"""
    from collections import OrderedDict
    data = '{"b": 2, "a": 1, "c": 3}'
    parsed = json.loads(data, object_pairs_hook=OrderedDict)
    assert isinstance(parsed, OrderedDict)
    # 保序: b, a, c
    assert list(parsed.keys()) == ["b", "a", "c"]


def test_json_parse_float():
    """真 parse_float 真 callable"""
    data = "1.5"
    result = json.loads(data, parse_float=lambda x: float(x) * 2)
    assert result == 3.0


# ======================== plistlib ========================
def test_plistlib_xml_roundtrip():
    """真 plistlib XML round-trip"""
    data = {
        "name": "Test",
        "version": 1.0,
        "items": [1, 2, 3],
        "nested": {"key": "value"},
    }
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".plist") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_XML)
        path = f.name
    try:
        with open(path, "rb") as f:
            loaded = plistlib.load(f)
        assert loaded == data
    finally:
        os.unlink(path)


def test_plistlib_binary_roundtrip():
    """真 plistlib binary round-trip"""
    data = {"name": "Test", "count": 42}
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".plist") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)
        path = f.name
    try:
        with open(path, "rb") as f:
            loaded = plistlib.load(f)
        assert loaded == data
    finally:
        os.unlink(path)


# ======================== wave ========================
def test_wave_write_and_read():
    """真 wave 真写真读"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    try:
        # 写
        n_channels = 1
        sample_width = 2
        frame_rate = 44100
        n_frames = 1000
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(n_channels)
            w.setsampwidth(sample_width)
            w.setframerate(frame_rate)
            # 1000 frame
            frames = b"\x00\x01" * n_frames
            w.writeframes(frames)
        # 读
        with wave.open(wav_path, "rb") as w:
            assert w.getnchannels() == n_channels
            assert w.getsampwidth() == sample_width
            assert w.getframerate() == frame_rate
            assert w.getnframes() == n_frames
            data = w.readframes(n_frames)
        assert len(data) == 2000  # 1000 frames * 2 bytes
    finally:
        os.unlink(wav_path)


def test_wave_stereo():
    """真 wave stereo 真写"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    try:
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(8000)
            # 100 frames * 2 channels * 2 bytes = 400 bytes
            frames = b"\x00\x00" * 200
            w.writeframes(frames)
        with wave.open(wav_path, "rb") as w:
            assert w.getnchannels() == 2
            data = w.readframes(w.getnframes())
        assert len(data) == 400
    finally:
        os.unlink(wav_path)
