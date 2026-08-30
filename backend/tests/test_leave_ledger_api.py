"""年次有給休暇管理簿のテスト。"""
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.leave.models import (
    LeaveConsumption,
    LeaveRequest,
    LeaveRequestStatus,
    LeaveType,
    PaidLeaveGrant,
    PaidLeavePolicy,
)

pytestmark = pytest.mark.django_db


def test_ledger_lists_grants_with_consumptions(client, admin_user, employee):
    policy = PaidLeavePolicy.objects.create(name="標準")
    leave_type = LeaveType.objects.create(name="年次有給休暇", is_paid=True, counts_toward_mandatory_five=True)
    grant = PaidLeaveGrant.objects.create(
        user=employee, policy=policy, granted_on=date(2026, 1, 1), days=Decimal("20"), expires_on=date(2028, 1, 1)
    )
    lr = LeaveRequest.objects.create(
        user=employee,
        leave_type=leave_type,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 1),
        unit="full",
        days=Decimal("1"),
        status=LeaveRequestStatus.APPROVED,
    )
    LeaveConsumption.objects.create(grant=grant, leave_request=lr, days=Decimal("1"))

    client.force_login(admin_user)
    res = client.get(reverse("leave-admin-ledger"), {"user_id": employee.id})
    assert res.status_code == 200
    body = res.json()
    assert body["employee"]["name"] == employee.name
    assert len(body["grants"]) == 1
    row = body["grants"][0]
    assert row["days"] == 20.0
    assert row["remaining"] == 19.0
    assert row["consumptions"][0]["date_label"] == "2026-03-01"


def test_ledger_pdf_returns_pdf(client, admin_user, employee):
    client.force_login(admin_user)
    res = client.get(reverse("leave-admin-ledger-pdf"), {"user_id": employee.id})
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"


def test_non_admin_cannot_view_ledger(client, employee):
    client.force_login(employee)
    res = client.get(reverse("leave-admin-ledger"), {"user_id": employee.id})
    assert res.status_code == 403
