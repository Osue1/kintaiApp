"""ユーザー単位の36協定総合判定（月次+年次+特別条項+複数月平均+回数）。"""
import pytest

from apps.attendance.models import MonthlyAttendance
from apps.compliance.services.evaluation import evaluate_user_overtime
from apps.compliance.services.overtime import OvertimePolicy, Severity

pytestmark = pytest.mark.django_db

SPECIAL_POLICY = OvertimePolicy(special_clause_enabled=True)


def _seed_month(user, year_month: str, overtime_hours: float) -> None:
    MonthlyAttendance.objects.create(
        user=user, year_month=year_month, overtime_statutory_minutes=int(overtime_hours * 60)
    )


def test_evaluation_is_ok_when_nothing_exceeds(client, employee):
    result = evaluate_user_overtime(employee, OvertimePolicy(), "2026-08", current_month_minutes=10 * 60)
    assert result.severity == Severity.OK
    assert result.reasons == ()


def test_evaluation_flags_current_month_over_limit(client, employee):
    result = evaluate_user_overtime(employee, OvertimePolicy(), "2026-08", current_month_minutes=46 * 60)
    assert result.severity == Severity.CRITICAL
    assert any(r.kind == "monthly" for r in result.reasons)


def test_evaluation_flags_multi_month_average_violation(client, employee):
    # 直近5ヶ月分を高稼働にしておき、当月を含めた平均が80時間を超えるようにする
    for ym in ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]:
        _seed_month(employee, ym, overtime_hours=85)

    result = evaluate_user_overtime(employee, SPECIAL_POLICY, "2026-08", current_month_minutes=85 * 60)
    assert result.severity == Severity.VIOLATION
    assert any(r.kind == "multi_month_avg" for r in result.reasons)


def test_evaluation_counts_months_over_45_across_the_year(client, employee):
    for ym in ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]:
        _seed_month(employee, ym, overtime_hours=46)

    # 当月で7回目の45時間超えになる
    result = evaluate_user_overtime(employee, SPECIAL_POLICY, "2026-07", current_month_minutes=46 * 60)
    assert any(r.kind == "monthly_over_count" and r.severity == Severity.VIOLATION for r in result.reasons)


def test_evaluation_ignores_prior_year_months_for_annual_total(client, employee):
    _seed_month(employee, "2025-12", overtime_hours=100)  # 前年分は年間合計に含めない
    result = evaluate_user_overtime(employee, OvertimePolicy(), "2026-01", current_month_minutes=10 * 60)
    assert result.severity == Severity.OK
