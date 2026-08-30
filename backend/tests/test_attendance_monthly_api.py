"""勤怠明細（日次一覧）と月次締め申請のテスト。"""
import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_monthly_detail_lists_days_up_to_today(client, employee):
    client.force_login(employee)
    ym = timezone.localdate().strftime("%Y-%m")
    res = client.get(reverse("attendance-monthly"), {"ym": ym})
    assert res.status_code == 200
    body = res.json()
    assert body["year_month"] == ym
    assert body["status"] == "draft"
    assert len(body["days"]) == timezone.localdate().day


def test_submit_monthly_notifies_admin_and_sets_status(client, employee, admin_user):
    client.force_login(employee)
    ym = timezone.localdate().strftime("%Y-%m")
    res = client.post(reverse("attendance-monthly-submit"), {"year_month": ym}, content_type="application/json")
    assert res.status_code == 200
    assert res.json()["status"] == "submitted"

    from apps.notifications.models import Notification

    assert Notification.objects.filter(user=admin_user, category="approval", title__contains="月次勤怠").exists()

    detail = client.get(reverse("attendance-monthly"), {"ym": ym}).json()
    assert detail["status"] == "submitted"


def test_admin_approve_locks_month_against_further_submit_changes(client, employee, admin_user):
    client.force_login(employee)
    ym = timezone.localdate().strftime("%Y-%m")
    client.post(reverse("attendance-monthly-submit"), {"year_month": ym}, content_type="application/json")

    from apps.attendance.models import MonthlyAttendance

    monthly = MonthlyAttendance.objects.get(user=employee, year_month=ym)
    client.force_login(admin_user)
    res = client.post(reverse("attendance-admin-monthly-approve", args=[monthly.id]))
    assert res.status_code == 204

    client.force_login(employee)
    res = client.post(reverse("attendance-punch"), {"action": "in"}, content_type="application/json")
    assert res.status_code == 409
