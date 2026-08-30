"""有給の付与判定（設計書 第6.1章・第13.1章の境界値）。"""
from datetime import date
from decimal import Decimal

from apps.leave.services.grant import (
    GrantRuleRow,
    calc_attendance_rate,
    meets_attendance_requirement,
    months_between,
    resolve_grant_days,
)

STATUTORY_TABLE = (
    GrantRuleRow(6, Decimal("10")),
    GrantRuleRow(18, Decimal("11")),
    GrantRuleRow(30, Decimal("12")),
    GrantRuleRow(42, Decimal("14")),
    GrantRuleRow(54, Decimal("16")),
    GrantRuleRow(66, Decimal("18")),
    GrantRuleRow(78, Decimal("20")),
)


def test_months_between_exact_boundary():
    assert months_between(date(2024, 1, 15), date(2024, 7, 15)) == 6
    assert months_between(date(2024, 1, 15), date(2024, 7, 14)) == 5


def test_resolve_grant_days_picks_latest_reached_row():
    assert resolve_grant_days(STATUTORY_TABLE, months_of_service=6) == Decimal("10")
    assert resolve_grant_days(STATUTORY_TABLE, months_of_service=17) == Decimal("10")
    assert resolve_grant_days(STATUTORY_TABLE, months_of_service=18) == Decimal("11")
    assert resolve_grant_days(STATUTORY_TABLE, months_of_service=100) == Decimal("20")


def test_resolve_grant_days_none_before_first_milestone():
    assert resolve_grant_days(STATUTORY_TABLE, months_of_service=5) is None


def test_resolve_grant_days_respects_prorated_segment():
    rules = STATUTORY_TABLE + (GrantRuleRow(6, Decimal("7"), prorated_weekly_days=4),)
    assert resolve_grant_days(rules, months_of_service=6, weekly_days=4) == Decimal("7")
    assert resolve_grant_days(rules, months_of_service=6, weekly_days=None) == Decimal("10")


def test_attendance_rate_exactly_80_percent_meets_requirement():
    """出勤率 80.0% ちょうど（設計書 13.1 境界値）。"""
    rate = calc_attendance_rate(scheduled_days=100, attended_days=80)
    assert rate == Decimal("0.800")
    assert meets_attendance_requirement(rate, required_rate=Decimal("0.800")) is True


def test_attendance_rate_just_below_80_percent_fails():
    rate = calc_attendance_rate(scheduled_days=1000, attended_days=799)
    assert rate < Decimal("0.800")
    assert meets_attendance_requirement(rate, required_rate=Decimal("0.800")) is False
