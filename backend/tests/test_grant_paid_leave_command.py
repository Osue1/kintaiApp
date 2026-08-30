"""有給自動付与バッチ：繰越上限超過の強制失効（設計書 第6.2章）。"""
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.leave.models import PaidLeaveGrant, PaidLeaveGrantRule, PaidLeavePolicy

pytestmark = pytest.mark.django_db


@pytest.fixture
def policy_with_cap(db):
    policy = PaidLeavePolicy.objects.create(
        name="上限あり",
        carryover_limit_days=Decimal("10"),
        expiry_years=2,
        required_attendance_rate=Decimal("0"),  # このテストでは出勤率ゲートを無効化する
    )
    PaidLeaveGrantRule.objects.create(policy=policy, months_of_service=12, granted_days=Decimal("20"))
    return policy


def test_carryover_excess_is_expired_on_new_grant(employee, policy_with_cap):
    today = timezone.localdate()
    hire_date = today.replace(year=today.year - 1)
    employee.hire_date = hire_date
    employee.leave_policy = policy_with_cap
    employee.save()

    # 前年からの繰越として15日残っている状態を作る（上限10日を5日超過）
    PaidLeaveGrant.objects.create(
        user=employee,
        policy=policy_with_cap,
        granted_on=hire_date,
        days=Decimal("15"),
        expires_on=today.replace(year=today.year + 5),
        source_note="事前付与",
    )

    call_command("grant_paid_leave")

    old_grant = PaidLeaveGrant.objects.get(source_note__startswith="事前付与")
    assert old_grant.days == Decimal("10")
    assert "繰越上限超過により5.0日失効" in old_grant.source_note

    new_grant = PaidLeaveGrant.objects.get(source_note__startswith="勤続12ヶ月付与")
    assert new_grant.days == Decimal("20")

    from apps.notifications.models import Notification

    assert Notification.objects.filter(user=employee, title__contains="繰越上限超過により有給休暇が失効").exists()


def test_no_expiry_when_carryover_within_limit(employee, policy_with_cap):
    today = timezone.localdate()
    hire_date = today.replace(year=today.year - 1)
    employee.hire_date = hire_date
    employee.leave_policy = policy_with_cap
    employee.save()

    PaidLeaveGrant.objects.create(
        user=employee,
        policy=policy_with_cap,
        granted_on=hire_date,
        days=Decimal("8"),  # 上限10日以内
        expires_on=today.replace(year=today.year + 5),
        source_note="事前付与",
    )

    call_command("grant_paid_leave")

    old_grant = PaidLeaveGrant.objects.get(source_note__startswith="事前付与")
    assert old_grant.days == Decimal("8")
    assert "失効" not in old_grant.source_note


def test_unlimited_carryover_when_policy_has_no_cap(employee):
    policy = PaidLeavePolicy.objects.create(
        name="無制限", carryover_limit_days=None, required_attendance_rate=Decimal("0")
    )
    PaidLeaveGrantRule.objects.create(policy=policy, months_of_service=12, granted_days=Decimal("20"))

    today = timezone.localdate()
    hire_date = today.replace(year=today.year - 1)
    employee.hire_date = hire_date
    employee.leave_policy = policy
    employee.save()

    PaidLeaveGrant.objects.create(
        user=employee,
        policy=policy,
        granted_on=hire_date,
        days=Decimal("50"),
        expires_on=today.replace(year=today.year + 5),
        source_note="事前付与",
    )

    call_command("grant_paid_leave")

    old_grant = PaidLeaveGrant.objects.get(source_note__startswith="事前付与")
    assert old_grant.days == Decimal("50")
