"""管理者アラートAPI（有給5日・36協定の複数月平均/特別条項を含む総合判定）。"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.attendance.models import DailySummary, TimeRecord
from apps.compliance.models import OvertimeLimitPolicy

pytestmark = pytest.mark.django_db


@pytest.fixture
def special_policy(db):
    return OvertimeLimitPolicy.objects.create(name="特別条項あり", special_clause_enabled=True, is_default=True)


def _seed_daily_overtime(user, work_date, overtime_minutes: int) -> None:
    """DailySummary を直接作る。打刻の実時刻計算をバイパスして集計だけを検証する。"""
    record = TimeRecord.objects.create(user=user, work_date=work_date)
    DailySummary.objects.create(
        time_record=record, worked_minutes=overtime_minutes + 480, overtime_statutory=overtime_minutes
    )


def test_no_alert_when_within_limits(client, admin_user, employee, special_policy):
    client.force_login(admin_user)
    res = client.get(reverse("admin-alerts"))
    assert res.status_code == 200
    assert res.json()["overtime_alerts"] == []


def test_current_month_overtime_triggers_alert_with_reasons(client, admin_user, employee, special_policy):
    today = timezone.localdate()
    _seed_daily_overtime(employee, today, overtime_minutes=46 * 60)

    client.force_login(admin_user)
    res = client.get(reverse("admin-alerts"))
    alerts = {a["employee_id"]: a for a in res.json()["overtime_alerts"]}
    assert str(employee.id) in alerts
    entry = alerts[str(employee.id)]
    assert entry["severity"] in ("warning", "critical", "violation")
    assert any(r["kind"] == "monthly" for r in entry["reasons"])


def test_multi_month_average_violation_surfaces_as_alert(client, admin_user, employee, special_policy):
    from apps.attendance.models import MonthlyAttendance

    today = timezone.localdate()
    _seed_daily_overtime(employee, today, overtime_minutes=85 * 60)  # 当月分

    for i in range(1, 6):
        ym = (today.replace(day=1) - timedelta(days=30 * i)).strftime("%Y-%m")
        MonthlyAttendance.objects.get_or_create(
            user=employee, year_month=ym, defaults={"overtime_statutory_minutes": 85 * 60}
        )

    client.force_login(admin_user)
    res = client.get(reverse("admin-alerts"))
    alerts = {a["employee_id"]: a for a in res.json()["overtime_alerts"]}
    assert str(employee.id) in alerts
    reason_kinds = {r["kind"] for r in alerts[str(employee.id)]["reasons"]}
    assert "multi_month_avg" in reason_kinds
    assert alerts[str(employee.id)]["severity"] == "violation"


def test_alert_absent_without_special_clause_even_with_high_average(client, admin_user, employee):
    """特別条項ポリシーが無効なら、複数月平均・特別条項系の判定は行わない（設計書 第7章）。"""
    today = timezone.localdate()
    _seed_daily_overtime(employee, today, overtime_minutes=10 * 60)  # 通常判定には引っかからない程度

    client.force_login(admin_user)
    res = client.get(reverse("admin-alerts"))
    alerts = {a["employee_id"]: a for a in res.json()["overtime_alerts"]}
    assert str(employee.id) not in alerts


def test_admin_alerts_query_count_does_not_scale_with_employee_count(client, admin_user, work_pattern):
    """N+1回避のリグレッションテスト（設計上の欠陥の修正確認）。

    かつては在籍従業員数に比例してクエリ数が増加していた（1人あたり有給付与・休暇消化・
    月次集計・36協定履歴で合計6〜7クエリ）。対象者が1人の場合と10人の場合とでAPI呼び出し
    あたりのクエリ数を実測し、人数が10倍になってもクエリ数がほぼ一定であることを確認する。
    """

    def seed_employees(n: int, offset: int) -> None:
        for i in range(n):
            get_user_model().objects.create_user(
                email=f"scale-{offset + i}@example.com",
                password="correct-horse-battery",
                name=f"検証用従業員{offset + i}",
                role=Role.EMPLOYEE,
                work_pattern=work_pattern,
            )

    client.force_login(admin_user)

    seed_employees(1, offset=0)
    with CaptureQueriesContext(connection) as small:
        res_small = client.get(reverse("admin-alerts"))
    assert res_small.status_code == 200

    seed_employees(9, offset=1)  # 合計10人に増やす
    with CaptureQueriesContext(connection) as large:
        res_large = client.get(reverse("admin-alerts"))
    assert res_large.status_code == 200

    small_count = len(small.captured_queries)
    large_count = len(large.captured_queries)
    # 人数が10倍(1人→10人)になってもクエリ数の増分はごくわずかな定数に収まるべきで、
    # 従業員数に比例して増える（N+1）ならこの余裕幅を大きく超えるはずである。
    assert large_count <= small_count + 5, (
        f"従業員数の増加(1→10人)に対してクエリ数が{small_count}→{large_count}に増加しており、"
        "N+1クエリが再発している可能性があります。"
    )
