"""監査ログ（AuditLog）の実記録化（設計書 第12.1章「承認・打刻修正・マスタ変更・請求書発行を記録する」）。"""
import pytest
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import AuditLog
from apps.common.audit import record_audit

pytestmark = pytest.mark.django_db


def test_record_audit_captures_actor_ip_and_user_agent(admin_user):
    request = RequestFactory().post(
        "/api/v1/whatever", HTTP_USER_AGENT="pytest-agent", REMOTE_ADDR="203.0.113.5"
    )
    request.user = admin_user

    record_audit(request, "employee_update", "User", admin_user.id, before={"name": "旧"}, after={"name": "新"})

    log = AuditLog.objects.get(action="employee_update", target_type="User", target_id=admin_user.id)
    assert log.actor == admin_user
    assert log.ip == "203.0.113.5"
    assert log.user_agent == "pytest-agent"
    assert log.before == {"name": "旧"}
    assert log.after == {"name": "新"}


def test_record_audit_prefers_x_forwarded_for_over_remote_addr(admin_user):
    request = RequestFactory().post(
        "/api/v1/whatever", HTTP_X_FORWARDED_FOR="198.51.100.9, 10.0.0.1", REMOTE_ADDR="10.0.0.1"
    )
    request.user = admin_user

    record_audit(request, "employee_update", "User", admin_user.id)

    log = AuditLog.objects.latest("id")
    assert log.ip == "198.51.100.9"


def test_record_audit_swallows_write_failures(admin_user, monkeypatch):
    """監査ログの書き込み失敗が本処理（呼び出し元）を巻き込んで例外にならないこと。"""
    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(AuditLog.objects, "create", boom)
    request = RequestFactory().post("/api/v1/whatever")
    request.user = admin_user

    record_audit(request, "employee_update", "User", admin_user.id)  # 例外を投げない


def test_correction_approve_writes_audit_log(client, employee, admin_user):
    client.force_login(employee)
    res = client.post(
        reverse("attendance-corrections"),
        {"date": "2026-08-20", "type": "clock_out", "corrected_time": "19:45", "reason": "客先対応のため"},
        content_type="application/json",
    )
    correction_id = res.json()["id"]

    client.force_login(admin_user)
    client.post(reverse("attendance-admin-correction-approve", args=[correction_id]))

    log = AuditLog.objects.get(action="correction_approve", target_type="TimeCorrectionRequest", target_id=correction_id)
    assert log.actor == admin_user


def test_leave_approve_writes_audit_log(client, employee, admin_user):
    from decimal import Decimal

    from apps.leave.models import LeaveType, PaidLeaveGrant, PaidLeavePolicy

    policy = PaidLeavePolicy.objects.create(name="標準", required_attendance_rate=Decimal("0"))
    employee.leave_policy = policy
    employee.save()
    leave_type = LeaveType.objects.create(
        name="年次有給休暇", is_paid=True, supports_half_day=True, counts_toward_mandatory_five=True
    )
    PaidLeaveGrant.objects.create(
        user=employee, policy=policy, granted_on="2026-01-01", days=Decimal("10"), expires_on="2028-01-01"
    )

    client.force_login(employee)
    res = client.post(
        reverse("leave-requests"),
        {"type_id": leave_type.id, "unit": "full", "start_date": "2026-09-03", "end_date": "2026-09-03", "reason": ""},
        content_type="application/json",
    )
    assert res.status_code == 201, res.json()
    request_id = res.json()["id"]

    client.force_login(admin_user)
    res = client.post(reverse("leave-admin-approve", args=[request_id]))
    assert res.status_code == 204

    log = AuditLog.objects.get(action="leave_approve", target_type="LeaveRequest", target_id=request_id)
    assert log.actor == admin_user


def test_employee_update_writes_audit_log_with_before_after(client, employee, admin_user):
    client.force_login(admin_user)
    res = client.patch(
        reverse("employees-detail", args=[employee.id]),
        {"name": "新しい名前"},
        content_type="application/json",
    )
    assert res.status_code == 200

    log = AuditLog.objects.get(action="employee_update", target_type="User", target_id=employee.id)
    assert log.before["name"] == "山田太郎"
    assert log.after["name"] == "新しい名前"


def test_contractor_create_writes_audit_log(client, admin_user):
    client.force_login(admin_user)
    res = client.post(
        reverse("contractors-list"),
        {
            "name": "テスト外注先",
            "rate_type": "hourly",
            "rate_amount": "4500",
            "closing_day": 31,
            "payment_month_offset": 1,
            "payment_day": 10,
        },
        content_type="application/json",
    )
    assert res.status_code == 201, res.json()
    contractor_id = res.json()["id"]

    log = AuditLog.objects.get(action="contractor_create", target_type="Contractor", target_id=contractor_id)
    assert log.actor == admin_user
    assert log.after["name"] == "テスト外注先"


def test_contractor_work_record_save_writes_audit_log_with_before_after(client, admin_user):
    from apps.contractors.models import Contractor, ContractorRate

    contractor = Contractor.objects.create(name="外注先A", closing_day=31, payment_month_offset=1, payment_day=10)
    ContractorRate.objects.create(contractor=contractor, rate_type="hourly", rate_amount="4500", effective_from="2026-01-01")

    client.force_login(admin_user)
    res = client.post(
        reverse("contractors-work-records"),
        {"contractor_id": contractor.id, "year_month": "2026-08", "hours": "10.0"},
        content_type="application/json",
    )
    assert res.status_code == 200, res.json()
    record_id = res.json()["id"]

    log1 = AuditLog.objects.get(action="contractor_work_record_save", target_type="ContractorWorkRecord", target_id=record_id)
    assert log1.before is None
    assert log1.after["hours"] == "10.0"

    res = client.post(
        reverse("contractors-work-records"),
        {"contractor_id": contractor.id, "year_month": "2026-08", "hours": "12.5"},
        content_type="application/json",
    )
    assert res.status_code == 200

    logs = AuditLog.objects.filter(
        action="contractor_work_record_save", target_type="ContractorWorkRecord", target_id=record_id
    ).order_by("id")
    assert logs.count() == 2
    assert logs[1].before["hours"] == "10.0"
    assert logs[1].after["hours"] == "12.5"
