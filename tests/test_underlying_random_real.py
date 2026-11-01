# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""真 random"""
import random
import pytest

def test_random_mersenne_twister_seed():
    random.seed(42)
    seq1 = [random.random() for _ in range(10)]
    random.seed(42)
    seq2 = [random.random() for _ in range(10)]
    assert seq1 == seq2

def test_random_state_save_restore():
    random.seed(123)
    a = [random.random() for _ in range(5)]
    state = random.getstate()
    b = [random.random() for _ in range(5)]
    random.setstate(state)
    c = [random.random() for _ in range(5)]
    assert c == b
    assert a != c

def test_random_choices_real():
    random.seed(42)
    items = ["a", "b", "c", "d", "e"]
    weights = [1, 2, 3, 4, 5]
    picks = random.choices(items, weights=weights, k=1000)
    from collections import Counter
    counts = Counter(picks)
    assert counts["e"] > counts["a"]
    assert counts["a"] > 0

def test_random_sample_no_replace():
    s = random.sample(range(100), 10)
    assert len(s) == 10
    assert len(set(s)) == 10

def test_random_shuffle_real():
    items = list(range(100))
    original = list(items)
    random.seed(42)
    random.shuffle(items)
    assert len(items) == 100
    assert sorted(items) == original
    diffs = sum(1 for a, b in zip(items, original) if a != b)
    assert diffs > 50

def test_random_randint_range():
    random.seed(42)
    for _ in range(100):
        n = random.randint(1, 6)
        assert 1 <= n <= 6
    random.seed(42)
    for _ in range(100):
        n = random.randrange(0, 10)
        assert 0 <= n < 10

def test_random_gauss_distribution():
    random.seed(42)
    samples = [random.gauss(0, 1) for _ in range(10000)]
    mean = sum(samples) / len(samples)
    assert abs(mean) < 0.1
    var = sum((x - mean) ** 2 for x in samples) / len(samples)
    assert 0.9 < var ** 0.5 < 1.1

def test_random_uniform_real():
    random.seed(42)
    for _ in range(100):
        x = random.uniform(1.0, 2.0)
        assert 1.0 <= x <= 2.0
    random.seed(42)
    for _ in range(100):
        x = random.random()
        assert 0.0 <= x < 1.0

def test_system_random_real_os_urandom():
    sr = random.SystemRandom()
    s = {sr.random() for _ in range(1000)}
    assert len(s) == 1000
    ints = {sr.randint(0, 1 << 30) for _ in range(1000)}
    assert len(ints) == 1000
    assert len(sr.randbytes(32)) == 32

def test_random_betavariate_triangular():
    random.seed(42)
    samples = [random.betavariate(2, 5) for _ in range(1000)]
    mean = sum(samples) / len(samples)
    assert 0.2 < mean < 0.4
    samples = [random.triangular(0, 10, 5) for _ in range(1000)]
    for s in samples:
        assert 0 <= s <= 10
    samples = [random.expovariate(2.0) for _ in range(1000)]
    mean = sum(samples) / len(samples)
    assert 0.4 < mean < 0.6

def test_random_vonmises_choice():
    random.seed(42)
    angles = [random.vonmisesvariate(0, 20) for _ in range(2000)]
    in_range = sum(1 for a in angles if -1.5 < a < 1.5)
    assert in_range > 1000

def test_random_pareto_lognorm():
    random.seed(42)
    samples = sorted([random.paretovariate(1) for _ in range(1000)])
    assert 1.0 < samples[500] < 3.0
    samples = [random.lognormvariate(0, 1) for _ in range(1000)]
    mean = sum(samples) / len(samples)
    assert 1.0 < mean < 3.0

def test_random_secrets_quality():
    import secrets
    tokens = {secrets.token_hex(16) for _ in range(1000)}
    assert len(tokens) == 1000
    t = secrets.token_hex(16)
    assert len(t) == 32
    u = secrets.token_urlsafe(16)
    assert "+" not in u
    assert "/" not in u
    assert len(secrets.token_bytes(8)) == 8
    assert secrets.compare_digest(b"abc", b"abc")
    assert not secrets.compare_digest(b"abc", b"abd")
