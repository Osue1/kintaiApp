"""休暇申請・承認フローの統合テスト（FIFO消化が実際に記録されることを確認する）。"""
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.leave.models import LeaveType, PaidLeaveGrant, PaidLeavePolicy

pytestmark = pytest.mark.django_db


@pytest.fixture
def paid_leave_type(db):
    return LeaveType.objects.create(
        name="年次有給休暇", is_paid=True, supports_half_day=True, counts_toward_mandatory_five=True
    )


@pytest.fixture
def policy(db):
    return PaidLeavePolicy.objects.create(name="標準", required_attendance_rate=Decimal("0.800"))


@pytest.fixture
def granted_employee(employee, policy):
    today = timezone.localdate()
    PaidLeaveGrant.objects.create(
        user=employee, policy=policy, granted_on=today - timedelta(days=30), days=Decimal("5"), expires_on=today + timedelta(days=700)
    )
    return employee


def test_create_request_rejected_when_balance_insufficient(client, granted_employee, paid_leave_type):
    client.force_login(granted_employee)
    today = timezone.localdate()
    res = client.post(
        reverse("leave-requests"),
        {
            "type_id": paid_leave_type.id,
            "start_date": str(today + timedelta(days=5)),
            "end_date": str(today + timedelta(days=10)),
            "unit": "full",
            "reason": "",
        },
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.json()["code"] == "insufficient_balance"


def test_approve_request_consumes_balance_via_fifo(client, granted_employee, admin_user, paid_leave_type):
    client.force_login(granted_employee)
    today = timezone.localdate()
    res = client.post(
        reverse("leave-requests"),
        {
            "type_id": paid_leave_type.id,
            "start_date": str(today + timedelta(days=5)),
            "end_date": str(today + timedelta(days=6)),
            "unit": "full",
            "reason": "",
        },
        content_type="application/json",
    )
    assert res.status_code == 201
    request_id = res.json()["id"]

    client.force_login(admin_user)
    res = client.post(reverse("leave-admin-approve", args=[request_id]))
    assert res.status_code == 204

    client.force_login(granted_employee)
    balance = client.get(reverse("leave-balance")).json()
    assert balance["paid_remaining"] == 3.0

    from apps.leave.models import LeaveConsumption

    assert LeaveConsumption.objects.filter(leave_request_id=request_id).exists()


def test_reject_request_does_not_consume_balance(client, granted_employee, admin_user, paid_leave_type):
    client.force_login(granted_employee)
    today = timezone.localdate()
    res = client.post(
        reverse("leave-requests"),
        {
            "type_id": paid_leave_type.id,
            "start_date": str(today + timedelta(days=5)),
            "end_date": str(today + timedelta(days=5)),
            "unit": "full",
            "reason": "",
        },
        content_type="application/json",
    )
    request_id = res.json()["id"]

    client.force_login(admin_user)
    res = client.post(reverse("leave-admin-reject", args=[request_id]), {"reason": "日程調整をお願いします"}, content_type="application/json")
    assert res.status_code == 204

    client.force_login(granted_employee)
    balance = client.get(reverse("leave-balance")).json()
    assert balance["paid_remaining"] == 5.0


def test_approving_already_approved_request_returns_409(client, granted_employee, admin_user, paid_leave_type):
    """承認ボタンの二重クリック等で同じ申請を2回承認しようとしても、2回消化されないこと。"""
    client.force_login(granted_employee)
    today = timezone.localdate()
    res = client.post(
        reverse("leave-requests"),
        {
            "type_id": paid_leave_type.id,
            "start_date": str(today + timedelta(days=5)),
            "end_date": str(today + timedelta(days=6)),
            "unit": "full",
            "reason": "",
        },
        content_type="application/json",
    )
    request_id = res.json()["id"]

    client.force_login(admin_user)
    first = client.post(reverse("leave-admin-approve", args=[request_id]))
    assert first.status_code == 204
    second = client.post(reverse("leave-admin-approve", args=[request_id]))
    assert second.status_code == 409
    assert second.json()["code"] == "already_processed"

    from apps.leave.models import LeaveConsumption

    # 承認は1回分しか記録されない（二重消化されていない）
    assert LeaveConsumption.objects.filter(leave_request_id=request_id).count() == 1


def test_rejecting_already_approved_request_returns_409(client, granted_employee, admin_user, paid_leave_type):
    """承認済みの申請を後から差し戻そうとしても、状態が食い違わないよう拒否されること。"""
    client.force_login(granted_employee)
    today = timezone.localdate()
    res = client.post(
        reverse("leave-requests"),
        {
            "type_id": paid_leave_type.id,
            "start_date": str(today + timedelta(days=5)),
            "end_date": str(today + timedelta(days=5)),
            "unit": "full",
            "reason": "",
        },
        content_type="application/json",
    )
    request_id = res.json()["id"]

    client.force_login(admin_user)
    assert client.post(reverse("leave-admin-approve", args=[request_id])).status_code == 204
    reject_res = client.post(
        reverse("leave-admin-reject", args=[request_id]), {"reason": "取り消したい"}, content_type="application/json"
    )
    assert reject_res.status_code == 409
    assert reject_res.json()["code"] == "already_processed"

    from apps.leave.models import LeaveRequest as LeaveRequestModel
    from apps.leave.models import LeaveRequestStatus

    assert LeaveRequestModel.objects.get(pk=request_id).status == LeaveRequestStatus.APPROVED


@pytest.mark.django_db(transaction=True)
def test_concurrent_approval_of_two_requests_does_not_overconsume_balance():
    """同一利用者の異なる2件の休暇申請が同時に承認されても、残日数を超えて消化されないこと（競合状態）。

    通常テストはトランザクションロールバックで分離するため別スレッドから状態が見えない。
    ここでは transaction=True（実DBへの本コミット）＋threading で実際に2つの承認リクエストを
    並行実行し、_grant_lots(..., for_update=True) による直列化が機能していることを検証する。
    5日付与のところ、3日の申請を2件（合計6日）同時承認しようとするので、両方成功すると
    残日数が -1 日になってしまう。片方は insufficient_balance で弾かれなければならない。
    """
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Role

    policy = PaidLeavePolicy.objects.create(name="並行検証用", required_attendance_rate=Decimal("0.800"))
    leave_type = LeaveType.objects.create(
        name="並行検証用有給", is_paid=True, supports_half_day=True, counts_toward_mandatory_five=True
    )
    employee = get_user_model().objects.create_user(
        email="race-leave-employee@example.com", password="correct-horse-battery", name="競合検証従業員",
    )
    admin = get_user_model().objects.create_user(
        email="race-leave-admin@example.com", password="correct-horse-battery", name="競合検証管理者", role=Role.ADMIN,
    )
    today = timezone.localdate()
    PaidLeaveGrant.objects.create(
        user=employee, policy=policy, granted_on=today - timedelta(days=30), days=Decimal("5"),
        expires_on=today + timedelta(days=700),
    )

    from apps.leave.models import LeaveRequest, LeaveRequestStatus

    requests = [
        LeaveRequest.objects.create(
            user=employee, leave_type=leave_type,
            start_date=today + timedelta(days=10 + i), end_date=today + timedelta(days=12 + i),
            unit="full", days=Decimal("3"),
        )
        for i in range(2)
    ]

    outcomes: list[int] = []
    start_barrier = threading.Barrier(2)

    def attempt_approve(pk: int) -> None:
        from django.db import connection
        from django.test import Client

        try:
            start_barrier.wait(timeout=5)
            c = Client()
            c.force_login(admin)
            res = c.post(reverse("leave-admin-approve", args=[pk]))
            outcomes.append(res.status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt_approve, args=(r.id,)) for r in requests]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(outcomes) == [204, 409]
    approved_count = LeaveRequest.objects.filter(id__in=[r.id for r in requests], status=LeaveRequestStatus.APPROVED).count()
    assert approved_count == 1

    from apps.leave.services.balance import active_lots, remaining_days
    from apps.leave.views import _grant_lots

    lots = _grant_lots(employee)
    remaining = remaining_days(lots, as_of=today)
    assert remaining == Decimal("2")  # 5日 - 3日消化 = 2日（マイナスになっていない）
    assert active_lots(lots, as_of=today)  # ロットは失効していない
