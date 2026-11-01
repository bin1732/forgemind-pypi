# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""statistics 模块中心趋势统计量的真实数值行为测试。

覆盖模块:statistics(标准库,CPython 3.11.2)。
真实测试项(18 项,全部对手算可验证的数据集断言具体数值):

  1. mean 对 [1,2,3,4] 给出 2.5
  2. mean 对空数据集抛 StatisticsError
  3. mean 对 Fraction 输入给出精确的 1/2,对 Decimal 输入给出精确的 0.15
  4. median 对偶数长度数据取中间两个的均值 2.5
  5. median 对奇数长度数据取正中值 3(乱序输入同样成立)
  6. median_low / median_high 把偶数中位数夹在 2 与 3 之间
  7. median_grouped 用组中点均值给出 2.5(interval=1)与 2.0(interval=2)
  8. mode 给出出现次数最多的值 1
  9. mode 在频率并列时给出最先出现的值
 10. multimode 给出全部并列众数 [1, 2] 与 [1, 3]
 11. fmean 与 fsum(data)/len(data) 逐位相等
 12. fmean 把 Decimal 输入转成 float 0.15...,与 mean 的精确值形成对照
 13. geometric_mean 对 [1,2,3,4] 给出 24 的四次方根 2.2133638394006434
 14. geometric_mean 对含 0 的数据集抛 StatisticsError
 15. harmonic_mean 对 [1,2,3,4] 给出 48/25 = 1.92
 16. harmonic_mean 对含 0 的数据集给出 0.0
 17. harmonic_mean 对含负数的数据集抛 StatisticsError
 18. 三个均值满足 调和平均 <= 几何平均 <= 算术平均 的次序
"""

import statistics
from decimal import Decimal
from fractions import Fraction

import pytest


# ======================== 算术平均 ========================
def test_mean_of_four_integers_is_two_and_a_half():
    """statistics.mean 对 [1,2,3,4] 求出的算术平均必须是 2.5。

    手算:(1+2+3+4)/4 = 10/4 = 2.5。
    """
    assert statistics.mean([1, 2, 3, 4]) == 2.5
    assert statistics.mean([1, 2, 3, 4, 5]) == 3.0
    assert statistics.mean([10, 20, 30, 40]) == 25.0


def test_mean_of_empty_dataset_raises_statistics_error():
    """空数据集求平均必须抛 StatisticsError,而不是返回 0 或 nan。"""
    with pytest.raises(statistics.StatisticsError, match="at least one data point"):
        statistics.mean([])


def test_mean_of_fractions_and_decimals_keeps_exact_result():
    """mean 对 Fraction / Decimal 输入保留精确值,不退化成二进制浮点近似。

    Fraction(1,3)+Fraction(2,3) = 1,除以 2 得精确的 1/2;
    Decimal("0.1")+Decimal("0.2") = 0.3,除以 2 得精确的 0.15。
    """
    frac_mean = statistics.mean([Fraction(1, 3), Fraction(2, 3)])
    assert frac_mean == Fraction(1, 2)
    assert isinstance(frac_mean, Fraction)

    dec_mean = statistics.mean([Decimal("0.1"), Decimal("0.2")])
    assert dec_mean == Decimal("0.15")
    assert isinstance(dec_mean, Decimal)


# ======================== 中位数 ========================
def test_median_of_even_length_dataset_averages_two_middle_values():
    """偶数长度数据的中位数是中间两个值的算术平均。

    [1,2,3,4] 的中间两个是 2 与 3,中位数为 (2+3)/2 = 2.5。
    """
    assert statistics.median([1, 2, 3, 4]) == 2.5
    assert statistics.median([10, 20, 30, 40]) == 25.0


def test_median_of_odd_length_dataset_is_the_middle_value():
    """奇数长度数据的中位数是正中那个元素本身,与输入顺序无关。"""
    assert statistics.median([1, 3, 5]) == 3
    assert statistics.median([5, 1, 3]) == 3
    assert statistics.median([7]) == 7


def test_median_low_and_high_bracket_the_even_median():
    """median_low 取中间偏小的值,median_high 取中间偏大的值,两者夹住中位数。

    [1,2,3,4]:median_low = 2,median_high = 3,median = 2.5。
    """
    assert statistics.median_low([1, 2, 3, 4]) == 2
    assert statistics.median_high([1, 2, 3, 4]) == 3
    assert statistics.median_low([1, 2, 3, 4]) <= statistics.median([1, 2, 3, 4])
    assert statistics.median([1, 2, 3, 4]) <= statistics.median_high([1, 2, 3, 4])


def test_median_grouped_averages_bin_midpoints():
    """median_grouped 先按固定宽度分箱,再用箱中点近似中位数。

    interval=1 时每个整数自成一箱,箱中点即原值,中位数为 2.5;
    interval=2 时分成 (0,2] 与 (2,4] 两箱,箱中点 1 与 3,中位数为 (1+3)/2 = 2.0。
    """
    assert statistics.median_grouped([1, 2, 3, 4]) == 2.5
    assert statistics.median_grouped([1, 2, 3, 4], 2) == 2.0


# ======================== 众数 ========================
def test_mode_returns_the_most_frequent_value():
    """mode 给出出现次数最多的那个值。

    [1,1,2,3] 中 1 出现 2 次,其余各 1 次,众数是 1。
    """
    assert statistics.mode([1, 1, 2, 3]) == 1
    assert statistics.mode(["red", "blue", "blue", "red", "green", "red", "red"]) == "red"


def test_mode_with_tied_frequencies_returns_first_encountered_value():
    """频率并列时 mode 返回最先遇到的那个值(CPython 3.11 起的行为)。"""
    assert statistics.mode([1, 2, 3]) == 1
    assert statistics.mode(["red", "red", "green", "blue", "blue"]) == "red"


def test_multimode_lists_every_tied_mode_in_sorted_order():
    """multimode 返回全部并列众数,按数值升序排列。"""
    assert statistics.multimode([1, 1, 2, 2, 3]) == [1, 2]
    assert statistics.multimode([1, 1, 2, 3, 3]) == [1, 3]
    assert statistics.multimode("aabbbbbbbbcc") == ["b"]


# ======================== 快速平均 ========================
def test_fmean_equals_fsum_divided_by_count():
    """fmean 用 math.fsum 做精确求和后除以个数,结果与 fsum/n 逐位相等。

    对 [1,2,3,4]:fsum = 10.0,除以 4 得 2.5。
    """
    for data in ([1, 2, 3, 4], [0.1, 0.2, 0.3], [0.1] * 10, [1e-16, 1.0, 1.0]):
        assert statistics.fmean(data) == statistics.fsum(data) / len(data)
    assert statistics.fmean([1, 2, 3, 4]) == 2.5
    assert statistics.fmean([0.1] * 10) == 0.1


def test_fmean_converts_decimal_input_to_float():
    """fmean 一律产出 float,Decimal 输入被转换后再参与浮点累加。

    mean([Decimal("0.1"), Decimal("0.2")]) 保留精确的 Decimal('0.15'),
    而 fmean 返回 float 0.15000000000000002。
    """
    value = statistics.fmean([Decimal("0.1"), Decimal("0.2")])
    assert isinstance(value, float)
    assert value == 0.15000000000000002
    assert statistics.mean([Decimal("0.1"), Decimal("0.2")]) == Decimal("0.15")


# ======================== 几何平均 ========================
def test_geometric_mean_of_four_values_is_fourth_root_of_24():
    """geometric_mean 给出连乘积的 n 次方根。

    [1,2,3,4] 的连乘积是 24,四次方根约等于 2.2133638394006434。
    """
    assert statistics.geometric_mean([1, 2, 3, 4]) == pytest.approx(24 ** 0.25, abs=1e-12)
    assert statistics.geometric_mean([1, 2, 3, 4]) == pytest.approx(2.2133638394006434, abs=1e-12)
    assert statistics.geometric_mean([4, 4, 4]) == pytest.approx(4.0, abs=1e-12)


def test_geometric_mean_rejects_non_positive_values():
    """含 0 或负数的数据集没有几何平均,必须抛 StatisticsError。"""
    with pytest.raises(statistics.StatisticsError, match="positive numbers"):
        statistics.geometric_mean([0, 1, 2])
    with pytest.raises(statistics.StatisticsError, match="positive numbers"):
        statistics.geometric_mean([-1, 2, 3])


# ======================== 调和平均 ========================
def test_harmonic_mean_of_four_values_is_48_over_25():
    """harmonic_mean 给出倒数的算术平均的倒数。

    [1,2,3,4] 的倒数和是 1+1/2+1/3+1/4 = 25/12,取倒数得 4/(25/12) = 48/25 = 1.92。
    """
    assert statistics.harmonic_mean([1, 2, 3, 4]) == pytest.approx(48 / 25, abs=1e-12)
    assert statistics.harmonic_mean([1, 2, 3, 4]) == pytest.approx(1.92, abs=1e-12)
    assert statistics.harmonic_mean([2, 2, 2, 2]) == pytest.approx(2.0, abs=1e-12)


def test_harmonic_mean_of_dataset_containing_zero_is_zero():
    """数据集中含 0 时调和平均为 0(CPython 3.11 起不再抛异常)。"""
    assert statistics.harmonic_mean([0, 1, 2]) == 0.0
    assert statistics.harmonic_mean([0, 0, 5]) == 0.0


def test_harmonic_mean_rejects_negative_values():
    """含负数的数据集没有调和平均,必须抛 StatisticsError。"""
    with pytest.raises(statistics.StatisticsError, match="negative values"):
        statistics.harmonic_mean([-1, 1, 2])


def test_three_means_keep_the_arithmetic_geometric_harmonic_order():
    """同一组正数上,调和平均 <= 几何平均 <= 算术平均,三者都小于等于最大值。

    [1,2,3,4]:调和 1.92 < 几何 2.2133638394006434 < 算术 2.5 < 最大值 4。
    """
    data = [1, 2, 3, 4]
    harmonic = statistics.harmonic_mean(data)
    geometric = statistics.geometric_mean(data)
    arithmetic = statistics.mean(data)
    assert harmonic < geometric < arithmetic
    assert arithmetic == 2.5
    assert geometric == pytest.approx(24 ** 0.25, abs=1e-12)
    assert harmonic == pytest.approx(48 / 25, abs=1e-12)
    assert harmonic == pytest.approx(4 / (1 + 0.5 + 1 / 3 + 0.25), abs=1e-12)
