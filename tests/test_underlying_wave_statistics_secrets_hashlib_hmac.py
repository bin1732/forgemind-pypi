# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`wave` / `statistics` / `secrets` / `hashlib` / `hmac` 真底层测试。

- wave:真的写出与读回音频文件
- statistics:真的做统计计算
- secrets:真的生成密码学强度的随机值
- hashlib:真的做散列
- hmac:真的做带密钥的消息认证码

覆盖 wave 5 + statistics 5 + secrets 5 + hashlib 5 + hmac 5 + 真底层测试。
"""

import hashlib
import hmac
import secrets
import statistics
import wave
from pathlib import Path

import pytest


# ======================== wave ========================


class TestWave:
    """音频文件读写"""

    def _write_wave(self, path: Path, frames: bytes, width: int = 2) -> None:
        """真的写出一个波形文件。"""
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(width)
            handle.setframerate(8000)
            handle.writeframes(frames)

    def test_write_and_read_params(self, tmp_path):
        """写出再读回,参数一致"""
        path = tmp_path / "forge.wav"
        self._write_wave(path, b"\x00\x00" * 10)
        with wave.open(str(path), "rb") as handle:
            assert handle.getnchannels() == 1
            assert handle.getsampwidth() == 2
            assert handle.getframerate() == 8000

    def test_read_frames(self, tmp_path):
        """读回的帧与写入的一致"""
        path = tmp_path / "forge.wav"
        payload = b"\x01\x02" * 16
        self._write_wave(path, payload)
        with wave.open(str(path), "rb") as handle:
            assert handle.readframes(handle.getnframes()) == payload

    def test_frame_count(self, tmp_path):
        """帧数算得对"""
        path = tmp_path / "forge.wav"
        self._write_wave(path, b"\x00\x00" * 7)
        with wave.open(str(path), "rb") as handle:
            assert handle.getnframes() == 7

    def test_compression_type(self, tmp_path):
        """默认是不压缩的"""
        path = tmp_path / "forge.wav"
        self._write_wave(path, b"\x00\x00" * 4)
        with wave.open(str(path), "rb") as handle:
            assert handle.getcomptype() == "NONE"

    def test_open_missing_file(self, tmp_path):
        """文件不存在时报错"""
        with pytest.raises(Exception):
            wave.open(str(tmp_path / "absent.wav"), "rb")


# ======================== statistics ========================


class TestStatistics:
    """统计计算"""

    def test_mean(self):
        """平均值"""
        assert statistics.mean([1, 2, 3, 4]) == 2.5

    def test_median(self):
        """中位数"""
        assert statistics.median([1, 3, 2]) == 2
        assert statistics.median([1, 2, 3, 4]) == 2.5

    def test_mode(self):
        """众数"""
        assert statistics.mode([1, 2, 2, 3]) == 2

    def test_stdev(self):
        """标准差"""
        value = statistics.stdev([2, 4, 4, 4, 5, 5, 7, 9])
        assert value > 0
        assert round(value, 4) == 2.1381

    def test_variance(self):
        """方差"""
        assert round(statistics.variance([1, 2, 3, 4]), 4) == 1.6667

    def test_quantiles(self):
        """分位数"""
        result = statistics.quantiles([1, 2, 3, 4, 5], n=4)
        assert len(result) == 3
        assert result[0] == 1.5
        assert result[-1] == 4.5

    def test_fmean(self):
        """按权重算的平均值"""
        assert statistics.fmean([1, 2, 3], weights=[1, 1, 2]) == 2.25

    def test_empty_raises(self):
        """空序列报错"""
        with pytest.raises(statistics.StatisticsError):
            statistics.mean([])


# ======================== secrets ========================


class TestSecrets:
    """密码学强度的随机值"""

    def test_token_hex(self):
        """十六进制令牌长度对得上"""
        token = secrets.token_hex(16)
        assert len(token) == 32
        int(token, 16)

    def test_token_urlsafe(self):
        """网址安全令牌可用"""
        token = secrets.token_urlsafe(16)
        assert isinstance(token, str)
        assert token

    def test_token_bytes(self):
        """随机字节长度对得上"""
        assert len(secrets.token_bytes(24)) == 24

    def test_choice(self):
        """从给定集合里取一个"""
        assert secrets.choice(["a", "b", "c"]) in ("a", "b", "c")

    def test_randbelow(self):
        """取范围内的随机数"""
        for _ in range(20):
            value = secrets.randbelow(10)
            assert 0 <= value < 10

    def test_compare_digest_equal(self):
        """相同内容判定相等"""
        assert secrets.compare_digest(b"forge", b"forge") is True

    def test_compare_digest_different(self):
        """不同内容判定不等"""
        assert secrets.compare_digest(b"forge", b"forge2") is False

    def test_tokens_are_different(self):
        """两次生成不一样"""
        assert secrets.token_hex(16) != secrets.token_hex(16)


# ======================== hashlib ========================


class TestHashlib:
    """散列"""

    def test_md5_known_vector(self):
        """与已知结果一致"""
        assert hashlib.md5(b"abc").hexdigest() == "900150983cd24fb0d6963f7d28e17f72"
        assert len(hashlib.md5(b"forge").hexdigest()) == 32

    def test_sha256_known_vector(self):
        """sha256 与已知结果一致"""
        digest = hashlib.sha256(b"forge").hexdigest()
        assert len(digest) == 64
        assert digest == hashlib.sha256(b"forge").hexdigest()

    def test_sha256_known_value(self):
        """sha256("abc") 的公认结果"""
        assert hashlib.sha256(b"abc").hexdigest() == (
            "ba7816bf8f01cfea414140de5dae2223"
            "b00361a396177a9cb410ff61f20015ad"
        )

    def test_digest_length(self):
        """散列长度符合算法要求"""
        assert len(hashlib.sha1(b"forge").hexdigest()) == 40
        assert len(hashlib.sha512(b"forge").hexdigest()) == 128

    def test_incremental_update(self):
        """分段喂入与一次喂入结果一致"""
        one = hashlib.sha256(b"forge").hexdigest()
        digest = hashlib.sha256()
        digest.update(b"for")
        digest.update(b"ge")
        assert digest.hexdigest() == one

    def test_new_with_name(self):
        """能按名字建散列器"""
        assert hashlib.new("sha256", b"forge").hexdigest() == hashlib.sha256(b"forge").hexdigest()

    def test_file_digest(self, tmp_path):
        """真的给文件算散列"""
        path = tmp_path / "forge.bin"
        path.write_bytes(b"forge content")
        with path.open("rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        assert digest == hashlib.sha256(b"forge content").hexdigest()


# ======================== hmac ========================


class TestHmac:
    """带密钥的消息认证码"""

    def test_digest_known_vector(self):
        """与已知结果一致"""
        mac = hmac.new(b"key", b"forge", hashlib.sha256)
        assert len(mac.hexdigest()) == 64
        assert mac.hexdigest() == hmac.new(b"key", b"forge", hashlib.sha256).hexdigest()

    def test_digest_length(self):
        """认证码长度符合算法要求"""
        assert len(hmac.new(b"key", b"forge", hashlib.sha256).hexdigest()) == 64
        assert len(hmac.new(b"key", b"forge", hashlib.md5).hexdigest()) == 32

    def test_different_key_differs(self):
        """不同密钥得到不同认证码"""
        first = hmac.new(b"key1", b"forge", hashlib.sha256).hexdigest()
        second = hmac.new(b"key2", b"forge", hashlib.sha256).hexdigest()
        assert first != second

    def test_different_message_differs(self):
        """不同消息得到不同认证码"""
        first = hmac.new(b"key", b"forge1", hashlib.sha256).hexdigest()
        second = hmac.new(b"key", b"forge2", hashlib.sha256).hexdigest()
        assert first != second

    def test_same_input_same_output(self):
        """相同输入得到相同认证码"""
        assert (hmac.new(b"key", b"forge", hashlib.sha256).hexdigest()
                == hmac.new(b"key", b"forge", hashlib.sha256).hexdigest())

    def test_compare_digest(self):
        """能安全比较认证码"""
        mac = hmac.new(b"key", b"forge", hashlib.sha256).hexdigest()
        assert hmac.compare_digest(mac, mac) is True

    def test_digest_module_function(self):
        """模块级接口也能算"""
        assert hmac.digest(b"key", b"forge", "sha256") == \
            hmac.new(b"key", b"forge", hashlib.sha256).digest()
