"""36協定の判定（設計書 第7章・第13.1章の境界値）。"""
from apps.compliance.services.overtime import (
    OvertimePolicy,
    Severity,
    judge_annual,
    judge_forecast,
    judge_monthly,
    judge_monthly_over_count,
    judge_multi_month_average,
    judge_special_annual,
    judge_special_monthly,
    landing_forecast_minutes,
    months_over_limit,
    rolling_averages,
)

POLICY = OvertimePolicy()
SPECIAL_POLICY = OvertimePolicy(special_clause_enabled=True)


def test_monthly_exactly_45_hours_is_critical():
    """月45時間ちょうど（設計書 13.1 境界値）。"""
    assert judge_monthly(45 * 60, POLICY) == Severity.CRITICAL


def test_monthly_just_under_45_hours_is_ok_or_warning():
    assert judge_monthly(45 * 60 - 1, POLICY) == Severity.WARNING  # 80%(36h)は超えている


def test_monthly_below_warning_threshold_is_ok():
    assert judge_monthly(int(45 * 60 * 0.79), POLICY) == Severity.OK


def test_special_monthly_100_hours_is_violation():
    """単月100時間ちょうどは違反（設計書 13.1 境界値）。"""
    assert judge_special_monthly(100 * 60, SPECIAL_POLICY) == Severity.VIOLATION
    assert judge_special_monthly(100 * 60 - 1, SPECIAL_POLICY) == Severity.OK


def test_special_monthly_not_evaluated_without_special_clause():
    assert judge_special_monthly(200 * 60, POLICY) == Severity.OK


def test_annual_360_hours_boundary():
    assert judge_annual(360 * 60, POLICY) == Severity.CRITICAL
    assert judge_annual(360 * 60 - 1, POLICY) == Severity.WARNING


def test_special_annual_720_hours_boundary():
    assert judge_special_annual(720 * 60, SPECIAL_POLICY) == Severity.VIOLATION
    assert judge_special_annual(720 * 60 - 1, SPECIAL_POLICY) == Severity.OK


def test_multi_month_average_80_hours_boundary():
    """2〜6ヶ月平均が80.0時間ちょうど（設計書 13.1 境界値）。"""
    assert judge_multi_month_average(80 * 60, SPECIAL_POLICY) == Severity.VIOLATION
    assert judge_multi_month_average(80 * 60 - 0.01, SPECIAL_POLICY) == Severity.OK


def test_monthly_over_count_5th_warning_7th_violation():
    """45時間超が年6回目と7回目（設計書 13.1 境界値）。"""
    assert judge_monthly_over_count(4, SPECIAL_POLICY) == Severity.OK
    assert judge_monthly_over_count(5, SPECIAL_POLICY) == Severity.WARNING
    assert judge_monthly_over_count(6, SPECIAL_POLICY) == Severity.WARNING
    assert judge_monthly_over_count(7, SPECIAL_POLICY) == Severity.VIOLATION


def test_landing_forecast_minutes_extrapolates_linearly():
    forecast = landing_forecast_minutes(elapsed_minutes=600, elapsed_business_days=10, total_business_days=20)
    assert forecast == 1200


def test_landing_forecast_zero_elapsed_days_is_zero():
    assert landing_forecast_minutes(elapsed_minutes=0, elapsed_business_days=0, total_business_days=20) == 0


def test_judge_forecast_over_limit_is_critical():
    assert judge_forecast(46 * 60, POLICY) == Severity.CRITICAL
    assert judge_forecast(37 * 60, POLICY) == Severity.WARNING
    assert judge_forecast(30 * 60, POLICY) == Severity.OK


def test_rolling_averages_skips_windows_without_enough_months():
    # 3ヶ月分しかないので window=2,3 だけ評価対象になる
    minutes = [100, 200, 300]
    averages = rolling_averages(minutes)
    assert averages == {2: 250.0, 3: 200.0}


def test_rolling_averages_uses_the_most_recent_months_per_window():
    minutes = [10, 20, 30, 40, 50, 60, 70]  # 7ヶ月分、window は最大6
    averages = rolling_averages(minutes)
    assert averages[2] == (60 + 70) / 2
    assert averages[6] == sum([20, 30, 40, 50, 60, 70]) / 6
    assert 7 not in averages


def test_months_over_limit_counts_months_meeting_or_exceeding():
    policy = OvertimePolicy()
    minutes = [45 * 60, 44 * 60, 45 * 60 + 1, 0]
    assert months_over_limit(minutes, policy) == 2
