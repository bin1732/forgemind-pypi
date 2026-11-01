# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""statistics 模块离散度与分位数的真实数值行为测试。

覆盖模块:statistics(标准库,CPython 3.11.2)。
真实测试项(18 项,离散度与分位点全部断到手算可验证的具体数值):

  1. pvariance 以 n 为分母,[1,2,3,4] 给出 5/4 = 1.25
  2. pstdev 是 pvariance 的正平方根,给出 1.118033988749895
  3. variance 以 n-1 为分母,[1,2,3,4] 给出 5/3 = 1.6666666666666667
  4. stdev 是 variance 的正平方根,给出 1.2909944487358056
  5. stdev 与 pstdev 相差 sqrt(n/(n-1)) 倍,即 1.2909944487358056
  6. 常量数据集的 variance 与 pstdev 都是 0
  7. 两个数时 pstdev 等于两者差值的一半(1.0),stdev 等于差值的 1/sqrt(2)
  8. quantiles 默认 exclusive 分位点为 [1.25, 2.5, 3.75]
  9. quantiles 的 inclusive 分位点为 [1.75, 2.5, 3.25]
 10. quantiles(n=2) 给出唯一的中位数分位点 2.5
 11. quantiles 对少于两个数据点的数据集抛 StatisticsError
 12. quantiles 对 n <= 0 抛 StatisticsError
 13. 两种方法的分位点都关于中位数 2.5 对称
 14. correlation 对完全线性序列给出 1.0,对反向序列给出 -1.0
 15. linear_regression 从 [1,2,3] -> [2,4,6] 还原出斜率 2.0 与截距 0.0
 16. statistics.kde / kde_random 的可用性严格对应 Python 3.13 起的版本门槛
 17. statistics.kde 的密度函数在 [-5,5] 上积分约为 1
 18. statistics.kde_random 的可用性严格对应 Python 3.13 起的版本门槛
"""

import math
import statistics
import sys

import pytest

# kde / kde_random 是 CPython 3.13 才加入的 API,3.12 及更早版本上不存在。
HAS_KDE = hasattr(statistics, "kde")
HAS_KDE_RANDOM = hasattr(statistics, "kde_random")

# ======================== 总体方差与总体标准差 ========================
def test_pvariance_uses_population_denominator():
    """pvariance 以 n 为分母,给出总体方差。

    [1,2,3,4] 的均值是 2.5,离均差平方和为 2.25+0.25+0.25+2.25 = 5,
    除以 n = 4 得 1.25。
    """
    assert statistics.pvariance([1, 2, 3, 4]) == pytest.approx(1.25, abs=1e-12)
    assert statistics.pvariance([1, 2, 3, 4]) == pytest.approx(5 / 4, abs=1e-12)
    assert statistics.pvariance([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(4.0, abs=1e-12)


def test_pstdev_is_positive_square_root_of_pvariance():
    """pstdev 是 pvariance 的正平方根,不能是负根。"""
    data = [1, 2, 3, 4]
    assert statistics.pstdev(data) == pytest.approx(math.sqrt(1.25), abs=1e-12)
    assert statistics.pstdev(data) == pytest.approx(1.118033988749895, abs=1e-12)
    assert statistics.pstdev(data) == pytest.approx(statistics.pvariance(data) ** 0.5, abs=1e-12)
    assert statistics.pstdev(data) > 0


def test_variance_uses_sample_denominator_n_minus_one():
    """variance 以 n-1 为分母,给出样本方差,数值大于同数据的总体方差。

    [1,2,3,4]:5 / 3 = 1.6666666666666667。
    """
    data = [1, 2, 3, 4]
    assert statistics.variance(data) == pytest.approx(5 / 3, abs=1e-12)
    assert statistics.variance(data) == pytest.approx(1.6666666666666667, abs=1e-12)
    assert statistics.variance(data) > statistics.pvariance(data)
    assert statistics.variance(data) == pytest.approx(5 / 3, abs=1e-12)


def test_stdev_is_positive_square_root_of_variance():
    """stdev 是 variance 的正平方根。"""
    data = [1, 2, 3, 4]
    assert statistics.stdev(data) == pytest.approx(math.sqrt(5 / 3), abs=1e-12)
    assert statistics.stdev(data) == pytest.approx(1.2909944487358056, abs=1e-12)
    assert statistics.stdev(data) == pytest.approx(statistics.variance(data) ** 0.5, abs=1e-12)
    assert statistics.stdev(data) > 0


def test_stdev_scales_pstdev_by_sqrt_n_over_n_minus_one():
    """样本标准差与总体标准差之间满足 stdev = pstdev * sqrt(n/(n-1))。

    n = 4 时 sqrt(4/3) = 1.1547005383792515,乘上 1.118033988749895 得
    1.2909944487358056。
    """
    data = [1, 2, 3, 4]
    n = len(data)
    assert statistics.stdev(data) == pytest.approx(
        statistics.pstdev(data) * math.sqrt(n / (n - 1)), abs=1e-12
    )
    assert statistics.stdev(data) == pytest.approx(
        1.118033988749895 * 1.1547005383792515, abs=1e-12
    )
    assert statistics.stdev(data) == pytest.approx(1.2909944487358056, abs=1e-12)


def test_variance_of_constant_dataset_is_zero():
    """所有取值相同时,方差与标准差都是 0。"""
    assert statistics.variance([5, 5, 5, 5]) == 0
    assert float(statistics.variance([5, 5, 5, 5])) == 0.0
    assert statistics.pvariance([5, 5, 5, 5]) == 0
    assert statistics.pstdev([5, 5, 5, 5]) == 0.0
    assert statistics.stdev([5, 5, 5, 5]) == 0.0


def test_pstdev_of_two_values_is_half_the_absolute_difference():
    """两个数时,总体标准差是两者差值的一半,样本标准差是差值除以 sqrt(2)。

    [1,3]:总体方差 = (1+1)/2 = 1,总体标准差 = 1;
    样本方差 = 2/1 = 2,样本标准差 = 1.4142135623730951。
    """
    assert statistics.pstdev([1, 3]) == pytest.approx(1.0, abs=1e-12)
    assert statistics.pvariance([1, 3]) == pytest.approx(1.0, abs=1e-12)
    assert statistics.stdev([1, 3]) == pytest.approx(math.sqrt(2), abs=1e-12)
    assert statistics.stdev([1, 3]) == pytest.approx(1.4142135623730951, abs=1e-12)
    assert statistics.variance([1, 3]) == pytest.approx(2.0, abs=1e-12)


# ======================== 分位数 ========================
def test_quantiles_exclusive_method_on_four_values():
    """quantiles 默认用 exclusive 方法,分位点落在被切分的区间内。

    [1,2,3,4] 分成 4 段,切点位置为 (n+1)*p/4 = 0.25, 1.25, 2.25, 3.25,
    线性插值得 1.25, 2.5, 3.75。
    """
    assert statistics.quantiles([1, 2, 3, 4], n=4) == pytest.approx(
        [1.25, 2.5, 3.75], abs=1e-12
    )
    assert statistics.quantiles([1, 2, 3, 4], n=4, method="exclusive") == pytest.approx(
        [1.25, 2.5, 3.75], abs=1e-12
    )


def test_quantiles_inclusive_method_on_four_values():
    """quantiles 的 inclusive 方法按 (n-1)*p 定位,分位点为 1.75, 2.5, 3.25。

    [1,2,3,4] 的切点位置为 0.25*3 = 0.75, 1.5, 2.25,
    线性插值得 1.75, 2.5, 3.25。
    """
    assert statistics.quantiles([1, 2, 3, 4], n=4, method="inclusive") == pytest.approx(
        [1.75, 2.5, 3.25], abs=1e-12
    )


def test_quantiles_with_n_two_returns_the_single_median():
    """n=2 时只切一刀,唯一分位点就是中位数 2.5。"""
    assert statistics.quantiles([1, 2, 3, 4], n=2) == pytest.approx([2.5], abs=1e-12)
    assert statistics.quantiles([1, 2, 3, 4], n=2)[0] == pytest.approx(
        statistics.median([1, 2, 3, 4]), abs=1e-12
    )


def test_quantiles_rejects_dataset_with_fewer_than_two_points():
    """只有一个数据点时无法切分,quantiles 必须抛 StatisticsError。"""
    with pytest.raises(statistics.StatisticsError, match="at least two data points"):
        statistics.quantiles([1], n=4)
    with pytest.raises(statistics.StatisticsError, match="at least two data points"):
        statistics.quantiles([], n=4)


def test_quantiles_rejects_non_positive_n():
    """n 必须是不小于 1 的整数,n = 0 时抛 StatisticsError。"""
    with pytest.raises(statistics.StatisticsError, match="n must be at least 1"):
        statistics.quantiles([1, 2, 3, 4], n=0)
    with pytest.raises(statistics.StatisticsError, match="n must be at least 1"):
        statistics.quantiles([1, 2, 3, 4], n=-3)


def test_quantiles_cut_points_are_symmetric_around_the_median():
    """两种切分方法的分位点都关于中位数 2.5 对称,首尾之和为 5.0。

    exclusive:[1.25, 2.5, 3.75];inclusive:[1.75, 2.5, 3.25]。
    """
    for method in ("exclusive", "inclusive"):
        cuts = statistics.quantiles([1, 2, 3, 4], n=4, method=method)
        assert cuts[0] + cuts[-1] == pytest.approx(5.0, abs=1e-12)
        assert cuts[1] == pytest.approx(2.5, abs=1e-12)
        assert cuts[0] < cuts[1] < cuts[-1]
    exclusive = statistics.quantiles([1, 2, 3, 4], n=4, method="exclusive")
    inclusive = statistics.quantiles([1, 2, 3, 4], n=4, method="inclusive")
    assert exclusive[0] == pytest.approx(1.25, abs=1e-12)
    assert inclusive[0] == pytest.approx(1.75, abs=1e-12)
    assert inclusive[0] > exclusive[0]


# ======================== 相关与回归 ========================
def test_correlation_of_perfectly_linear_series_is_one():
    """完全正相关的两组数据相关系数为 1,完全反相关为 -1。"""
    assert statistics.correlation([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0, abs=1e-12)
    assert statistics.correlation([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0, abs=1e-12)
    assert statistics.correlation([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0, abs=1e-12)


def test_linear_regression_recovers_slope_and_intercept():
    """linear_regression 从点集还原出最小二乘直线的斜率与截距。

    点集 (1,2) (2,4) (3,6) 落在 y = 2x 上,斜率 2.0、截距 0.0。
    """
    result = statistics.linear_regression([1, 2, 3], [2, 4, 6])
    assert result.slope == pytest.approx(2.0, abs=1e-12)
    assert result.intercept == pytest.approx(0.0, abs=1e-12)

    shifted = statistics.linear_regression([1, 2, 3], [3, 5, 7])
    assert shifted.slope == pytest.approx(2.0, abs=1e-12)
    assert shifted.intercept == pytest.approx(1.0, abs=1e-12)


# ======================== 3.13 才有的 KDE API ========================
def test_kde_api_availability_matches_interpreter_version():
    """statistics.kde 与 kde_random 只在 Python 3.13 起存在,版本门槛必须严丝合缝。

    解释器低于 3.13 时两个名字都取不到,达到 3.13 时两个名字都必须存在。
    """
    assert HAS_KDE == (sys.version_info >= (3, 13))
    assert HAS_KDE_RANDOM == (sys.version_info >= (3, 13))
    assert hasattr(statistics, "kde") == HAS_KDE
    assert hasattr(statistics, "kde_random") == HAS_KDE_RANDOM


@pytest.mark.skipif(not HAS_KDE, reason="statistics.kde 需要 Python 3.13 及以上")
def test_kde_density_integrates_to_one():
    """kde 给出的密度函数在整个实轴上积分为 1,且在数据中心附近取到峰值。

    数据 [1,2,3,4],网格取 [-5, 5] 步长 0.01,密度和乘步长应约为 1。
    """
    grid = [round(-5.0 + 0.01 * i, 2) for i in range(1001)]
    density = statistics.kde([1.0, 2.0, 3.0, 4.0], points=grid)
    values = density(grid)
    if not isinstance(values, (list, tuple)):
        values = [density(x) for x in grid]

    assert len(values) == len(grid)
    assert all(value >= 0.0 for value in values)

    mass = sum(values) * 0.01
    assert mass == pytest.approx(1.0, abs=0.02)

    peak = max(values)
    assert peak > 0.15
    assert values[grid.index(2.5)] == pytest.approx(peak, abs=1e-9)


def test_kde_random_api_availability_matches_interpreter_version():
    """statistics.kde_random 与 kde 同批引入,版本门槛一致,存在时可直接调用。"""
    assert hasattr(statistics, "kde_random") == (sys.version_info >= (3, 13))
    if HAS_KDE_RANDOM:
        assert callable(statistics.kde_random)
        samples = statistics.kde_random([1.0, 2.0, 3.0, 4.0], points=5)
        assert len(samples) == 5
        assert all(-3.0 <= value <= 8.0 for value in samples)
    else:
        assert not hasattr(statistics, "kde_random")
