"""打刻・打刻修正・月次承認の統合テスト。"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_punch_in_then_out_updates_dashboard(client, employee):
    client.force_login(employee)
    assert client.post(reverse("attendance-punch"), {"action": "in"}, content_type="application/json").status_code == 204

    dashboard = client.get(reverse("attendance-dashboard")).json()
    assert dashboard["today"]["state"] == "working"
    assert dashboard["today"]["clock_in_at"] is not None

    assert client.post(reverse("attendance-punch"), {"action": "out"}, content_type="application/json").status_code == 204
    dashboard = client.get(reverse("attendance-dashboard")).json()
    assert dashboard["today"]["state"] == "finished"


def test_correction_request_notifies_admins_and_admin_can_approve(client, employee, admin_user):
    client.force_login(employee)
    res = client.post(
        reverse("attendance-corrections"),
        {"date": "2026-08-20", "type": "clock_out", "corrected_time": "19:45", "reason": "客先対応のため"},
        content_type="application/json",
    )
    assert res.status_code == 201
    correction_id = res.json()["id"]

    from apps.notifications.models import Notification

    assert Notification.objects.filter(user=admin_user, category="approval").exists()

    client.force_login(admin_user)
    res = client.post(reverse("attendance-admin-correction-approve", args=[correction_id]))
    assert res.status_code == 204

    from django.utils import timezone

    from apps.attendance.models import TimeRecord

    record = TimeRecord.objects.get(user=employee, work_date="2026-08-20")
    assert timezone.localtime(record.clock_out_at).strftime("%H:%M") == "19:45"


def test_non_admin_cannot_approve_correction(client, employee):
    client.force_login(employee)
    client.post(
        reverse("attendance-corrections"),
        {"date": "2026-08-20", "type": "clock_out", "corrected_time": "19:45", "reason": "テスト"},
        content_type="application/json",
    )
    from apps.attendance.models import TimeCorrectionRequest

    correction = TimeCorrectionRequest.objects.first()
    res = client.post(reverse("attendance-admin-correction-approve", args=[correction.id]))
    assert res.status_code == 403


def test_monthly_lock_blocks_further_punches(client, employee, admin_user):
    from django.utils import timezone

    from apps.attendance.models import MonthlyAttendance, MonthlyStatus

    year_month = timezone.localdate().strftime("%Y-%m")
    MonthlyAttendance.objects.create(
        user=employee, year_month=year_month, status=MonthlyStatus.APPROVED, locked_at=timezone.now()
    )
    client.force_login(employee)
    res = client.post(reverse("attendance-punch"), {"action": "in"}, content_type="application/json")
    assert res.status_code == 409
