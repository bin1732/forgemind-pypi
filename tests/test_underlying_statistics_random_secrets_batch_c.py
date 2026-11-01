# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""random 与 secrets 模块的真实行为测试:可复现性、取值范围、权重与令牌格式。

覆盖模块:random(标准库,CPython 3.11.2)、secrets(标准库,CPython 3.11.2)。
真实测试项(18 项,全部断到具体数值或可复算的统计特征):

  1. 同一 seed 的两个 Random 实例给出完全相同的浮点序列,Random(42) 的前 5 个值固定
     为 0.6394267984578837 等确定值,不同 seed 则给出不同序列
  2. randint 覆盖闭区间两端,固定 seed 下前 10 个值为 2,5,1,3,1,4,4,4,6,4,
     上下界相同时只返回该值
  3. choice 返回给定序列中的元素,固定 seed 下 Random(11) 首取 'd'
  4. choices 的零权重元素永不被选中,cum_weights 与等价 weights 给出同一抽样序列
  5. choices 的 1:3 权重比在 400 次抽样中落到 100:300 附近
  6. shuffle 不改变元素的多重集合,固定 seed 下 Random(2) 给出确定的 20 元排列
  7. sample 取到互不相同的元素,且不改动源序列
  8. getrandbits 严格落在请求的位宽内,固定 seed 下 Random(3) 的 8 位结果为 60,151,139,33,94
  9. randbytes 的长度等于请求字节数,同一 seed 下字节序列相同
 10. random.Random.binomialvariate 的可用性严格对应 Python 3.12 起的版本门槛
 11. binomialvariate 的取值落在 [0, n] 内且均值接近 n*p
 12. token_bytes 的长度等于请求字节数(缺省 32),两次调用结果不同
 13. token_hex 的长度是请求字节数的两倍且字符集为小写十六进制
 14. token_urlsafe 的长度按 ceil(n*8/6) 计算,字符集为 URL 安全字母表
 15. secrets.randbelow 落在 [0, n) 半开区间内,且能取到 0 与 n-1
 16. secrets.randbits 严格落在请求的位宽内
 17. compare_digest 只对完全相同的内容返回 True
 18. secrets.SystemRandom 就是 random.SystemRandom,调用 seed 也不会让它可复现
"""

import random
import secrets
import string
import sys

import pytest

# binomialvariate 是 CPython 3.12 才加入的 API,3.11 及更早版本上不存在。
HAS_BINOMIALVARIATE = hasattr(random.Random, "binomialvariate")

# ======================== 随机数的可复现性 ========================
def test_seeded_generators_are_reproducible_and_seed_dependent():
    """同一 seed 的两个 Random 实例给出完全相同的序列,不同 seed 则给出不同序列。

    Random(42) 连取 5 个随机数,两个实例逐位相同,取值固定为
    0.6394267984578837, 0.025010755222666936, 0.27502931836911926,
    0.22321073814882275, 0.7364712141640124;
    Random(1) 与 Random(2) 的 20 个取值则互不相同。
    """
    first = random.Random(42)
    second = random.Random(42)
    assert [first.random() for _ in range(5)] == [second.random() for _ in range(5)]

    documented = random.Random(42)
    assert [documented.random() for _ in range(5)] == [
        0.6394267984578837,
        0.025010755222666936,
        0.27502931836911926,
        0.22321073814882275,
        0.7364712141640124,
    ]

    left = random.Random(1)
    right = random.Random(2)
    assert [left.random() for _ in range(20)] != [right.random() for _ in range(20)]


# ======================== 区间取整 ========================
def test_randint_covers_both_ends_of_the_range():
    """randint 的取值是闭区间 [a, b],两端都必须能被取到。

    Random(1) 连取 10 次 randint(1, 6) 的结果为 2,5,1,3,1,4,4,4,6,4;
    再抽 500 次,全部落在 [1, 6] 内且 1 与 6 都出现过;
    上下界相同时只返回该值。
    """
    rng = random.Random(1)
    assert [rng.randint(1, 6) for _ in range(10)] == [2, 5, 1, 3, 1, 4, 4, 4, 6, 4]

    draws = [random.Random(seed).randint(1, 6) for seed in range(500)]
    assert min(draws) == 1
    assert max(draws) == 6
    assert all(1 <= value <= 6 for value in draws)

    assert [random.Random(seed).randint(5, 5) for seed in range(10)] == [5] * 10


# ======================== 抽取元素 ========================
def test_choice_returns_member_of_the_given_sequence():
    """choice 返回给定序列里的元素,不能是别的值。

    Random(11) 连续 6 次从 "abcdef" 里取,结果为 d,e,d,d,e,e。
    """
    rng = random.Random(11)
    picked = [rng.choice("abcdef") for _ in range(6)]
    assert picked == ["d", "e", "d", "d", "e", "e"]
    assert all(value in "abcdef" for value in picked)

    population = [10, 20, 30]
    for seed in range(50):
        assert random.Random(seed).choice(population) in population


def test_choices_weights_control_which_element_is_picked():
    """choices 的零权重元素永不被选中,cum_weights 与等价 weights 给出同一序列。

    权重 [0.1, 0.3, 0.6] 的累积值是 [0.1, 0.4, 1.0],
    Random(9) 在两种写法下都给出 3,2,2,3,1,3。
    """
    rng = random.Random(1)
    picked = rng.choices([1, 2, 3], weights=[0, 1, 0], k=100)
    assert set(picked) == {2}
    assert len(picked) == 100

    by_weights = random.Random(9).choices([1, 2, 3], weights=[0.1, 0.3, 0.6], k=6)
    by_cum_weights = random.Random(9).choices([1, 2, 3], cum_weights=[0.1, 0.4, 1.0], k=6)
    assert by_weights == by_cum_weights
    assert by_weights == [3, 2, 2, 3, 1, 3]


def test_choices_weight_ratios_match_observed_frequencies():
    """choices 按权重比例分配命中次数,1:3 的权重在 400 次抽样中给出约 100:300。

    命中下标 0 的概率是 1/4,期望 100 次;标准差约 8.66,区间 [50, 150]
    距离期望超过 5 倍标准差。
    """
    rng = random.Random(1)
    picked = rng.choices([0, 1], weights=[1, 3], k=400)
    first_count = picked.count(0)
    second_count = picked.count(1)
    assert first_count + second_count == 400
    assert 50 <= first_count <= 150
    assert 250 <= second_count <= 350
    assert 0.2 <= first_count / 400 <= 0.3


# ======================== 洗牌与抽样 ========================
def test_shuffle_preserves_the_multiset_of_elements():
    """shuffle 只改变顺序,元素的多重集合必须保持不变。

    Random(2) 洗 [0..19] 得到 7,6,17,8,19,15,13,0,3,9,14,4,10,12,16,5,11,18,2,1,
    排序后与原序列完全一致;同 seed 的两次洗牌结果也完全一致。
    """
    values = list(range(20))
    random.Random(2).shuffle(values)
    assert values == [7, 6, 17, 8, 19, 15, 13, 0, 3, 9, 14, 4, 10, 12, 16, 5, 11, 18, 2, 1]
    assert sorted(values) == list(range(20))

    other = list(range(20))
    random.Random(2).shuffle(other)
    assert other == values


def test_sample_returns_distinct_elements_and_keeps_source_intact():
    """sample 取出的元素互不相同、都属于源序列,且不会改动源序列。

    Random(4).sample(range(20), 5) 给出 [7, 9, 3, 12, 15]。
    """
    population = list(range(20))
    picked = random.Random(4).sample(population, 5)
    assert picked == [7, 9, 3, 12, 15]
    assert len(picked) == 5
    assert len(set(picked)) == 5
    assert set(picked) <= set(population)
    assert population == list(range(20))

    repeated = random.Random(4).sample(population, 5)
    assert repeated == picked


# ======================== 位宽与字节 ========================
def test_getrandbits_stays_within_requested_bit_width():
    """getrandbits(k) 返回的整数严格落在 [0, 2^k) 内。

    Random(3) 连取 5 次 8 位结果为 60,151,139,33,94;
    16 位结果必须小于 65536,0 位结果恒为 0。
    """
    rng = random.Random(3)
    assert [rng.getrandbits(8) for _ in range(5)] == [60, 151, 139, 33, 94]

    for seed in range(50):
        assert 0 <= random.Random(seed).getrandbits(16) < 65536
        assert random.Random(seed).getrandbits(0) == 0


def test_randbytes_length_matches_request_and_is_reproducible():
    """randbytes(n) 返回 n 字节,同一 seed 的两个实例给出相同的字节。

    Random(8).randbytes(4) 的十六进制是 3365093a。
    """
    payload = random.Random(8).randbytes(4)
    assert len(payload) == 4
    assert payload.hex() == "3365093a"
    assert random.Random(8).randbytes(4) == payload
    assert len(random.Random(9).randbytes(16)) == 16


# ======================== 3.12 才有的二项分布抽样 ========================
def test_binomialvariate_api_availability_matches_interpreter_version():
    """random.Random.binomialvariate 只在 Python 3.12 起存在,版本门槛必须严丝合缝。"""
    assert HAS_BINOMIALVARIATE == (sys.version_info >= (3, 12))
    assert hasattr(random.Random, "binomialvariate") == HAS_BINOMIALVARIATE


@pytest.mark.skipif(
    not HAS_BINOMIALVARIATE,
    reason="random.Random.binomialvariate 需要 Python 3.12 及以上",
)
def test_binomialvariate_counts_stay_within_support():
    """binomialvariate(n, p) 取值落在 [0, n] 内,大量抽样的均值接近 n*p。

    n = 10、p = 0.5 时期望均值是 5,标准差约 1.58;
    200 次抽样的均值落在 [4, 6] 内的失败概率远低于 1%。
    """
    rng = random.Random(7)
    draws = [rng.binomialvariate(n=10, p=0.5) for _ in range(200)]
    assert all(0 <= value <= 10 for value in draws)
    assert all(isinstance(value, int) for value in draws)
    assert 4.0 <= sum(draws) / len(draws) <= 6.0


# ======================== secrets 令牌 ========================
def test_token_bytes_length_matches_requested_nbytes():
    """token_bytes(nbytes) 返回 nbytes 字节,缺省为 32 字节,两次调用结果不同。"""
    assert len(secrets.token_bytes(16)) == 16
    assert len(secrets.token_bytes(1)) == 1
    assert len(secrets.token_bytes()) == 32
    assert secrets.token_bytes(16) != secrets.token_bytes(16)
    assert isinstance(secrets.token_bytes(8), bytes)


def test_token_hex_length_is_twice_nbytes_with_lowercase_hex_alphabet():
    """token_hex(nbytes) 的十六进制串长度是 nbytes 的两倍,字符集为 0-9a-f。"""
    token = secrets.token_hex(16)
    assert len(token) == 32
    assert len(secrets.token_hex()) == 64
    assert set(token) <= set("0123456789abcdef")
    assert all(char in "0123456789abcdef" for char in secrets.token_hex(32))


def test_token_urlsafe_length_and_alphabet():
    """token_urlsafe(nbytes) 的长度是 ceil(nbytes*8/6),字符集为 URL 安全字母表。

    16 字节 -> 22 个字符,32 字节 -> 43 个字符;
    字母表是大小写字母、数字加上 '-' 与 '_'。
    """
    alphabet = set(string.ascii_letters + string.digits + "-_")
    token = secrets.token_urlsafe(16)
    assert len(token) == 22
    assert len(secrets.token_urlsafe(32)) == 43
    assert set(token) <= alphabet
    assert all(char in alphabet for char in secrets.token_urlsafe(24))


# ======================== secrets 随机取值 ========================
def test_randbelow_stays_in_half_open_range():
    """secrets.randbelow(n) 落在 [0, n) 半开区间内,且 0 与 n-1 都能取到。"""
    assert secrets.randbelow(1) == 0
    draws = [secrets.randbelow(10) for _ in range(200)]
    assert all(0 <= value < 10 for value in draws)
    assert min(draws) == 0
    assert max(draws) == 9


def test_randbits_stays_within_requested_bit_width():
    """secrets.randbits(k) 返回的整数严格落在 [0, 2^k) 内,0 位时恒为 0。"""
    for _ in range(100):
        assert 0 <= secrets.randbits(16) < 65536
        assert 0 <= secrets.randbits(8) < 256
    assert secrets.randbits(0) == 0


def test_compare_digest_accepts_only_equal_bytes():
    """compare_digest 只有在内容完全相同时才返回 True,长度不同也判为不等。"""
    assert secrets.compare_digest(b"abc", b"abc") is True
    assert secrets.compare_digest(b"abc", b"abd") is False
    assert secrets.compare_digest(b"abc", b"ab") is False
    assert secrets.compare_digest("abc", "abc") is True
    assert secrets.compare_digest("abc", "abd") is False


def test_secrets_system_random_matches_random_system_random():
    """secrets.SystemRandom 就是 random.SystemRandom,其取数不因 seed 而改变。

    两者是同一个类;secrets.randbelow 与 SystemRandom.randbelow 都取半开区间;
    即使给两个 SystemRandom 实例设同一个 seed,取到的 64 位随机数依然不同。
    """
    assert secrets.SystemRandom is random.SystemRandom
    assert isinstance(secrets.SystemRandom(), random.Random)

    assert all(0 <= secrets.randbelow(10) < 10 for _ in range(50))
    system_random = random.SystemRandom()
    assert all(0 <= random.randrange(10) < 10 for _ in range(50))
    assert all(0 <= system_random.randrange(10) < 10 for _ in range(50))
    assert all(0 <= system_random.randint(0, 9) < 10 for _ in range(50))
    assert all(0 <= system_random.getrandbits(8) < 256 for _ in range(50))

    first = random.SystemRandom()
    first.seed(42)
    second = random.SystemRandom()
    second.seed(42)
    assert first.getrandbits(64) != second.getrandbits(64)

    assert secrets.choice([1, 2, 3]) in (1, 2, 3)
