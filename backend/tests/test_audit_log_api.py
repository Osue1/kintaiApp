"""監査ログ閲覧API（設計上の欠陥の修正確認: Django管理サイト経由でしか確認できなかった監査ログを
アプリ内から閲覧できるようにする）。"""
from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AuditLog
from apps.common.audit import record_audit

pytestmark = pytest.mark.django_db


def _seed(actor, action: str, target_type: str, target_id: int, **extra) -> AuditLog:
    request = RequestFactory().post("/api/v1/whatever")
    request.user = actor
    record_audit(request, action, target_type, target_id, **extra)
    return AuditLog.objects.filter(action=action, target_type=target_type, target_id=target_id).latest("id")


def test_admin_can_list_audit_logs(client, admin_user, employee):
    _seed(admin_user, "employee_update", "User", employee.id, before={"name": "旧"}, after={"name": "新"})

    client.force_login(admin_user)
    res = client.get(reverse("admin-audit-logs"))
    assert res.status_code == 200
    body = res.json()
    assert body["total_count"] == 1
    assert body["truncated"] is False
    entry = body["results"][0]
    assert entry["actor_name"] == admin_user.name
    assert entry["action"] == "employee_update"
    assert entry["before"] == {"name": "旧"}
    assert entry["after"] == {"name": "新"}


def test_non_admin_cannot_list_audit_logs(client, employee):
    client.force_login(employee)
    res = client.get(reverse("admin-audit-logs"))
    assert res.status_code == 403


def test_filter_by_action(client, admin_user, employee):
    _seed(admin_user, "employee_update", "User", employee.id)
    _seed(admin_user, "invoice_send", "Invoice", 1)

    client.force_login(admin_user)
    res = client.get(reverse("admin-audit-logs"), {"action": "invoice_send"})
    body = res.json()
    assert body["total_count"] == 1
    assert body["results"][0]["action"] == "invoice_send"


def test_filter_by_target_type_and_target_id(client, admin_user, employee):
    _seed(admin_user, "employee_update", "User", employee.id)
    _seed(admin_user, "employee_update", "User", admin_user.id)

    client.force_login(admin_user)
    res = client.get(reverse("admin-audit-logs"), {"target_type": "User", "target_id": employee.id})
    body = res.json()
    assert body["total_count"] == 1
    assert body["results"][0]["target_id"] == employee.id


def test_filter_by_date_range(client, admin_user, employee):
    old_log = _seed(admin_user, "employee_update", "User", employee.id)
    AuditLog.objects.filter(pk=old_log.pk).update(created_at=timezone.now() - timedelta(days=10))
    _seed(admin_user, "invoice_send", "Invoice", 1)  # 直近分

    client.force_login(admin_user)
    today = timezone.localdate()
    res = client.get(reverse("admin-audit-logs"), {"date_from": str(today), "date_to": str(today)})
    body = res.json()
    assert body["total_count"] == 1
    assert body["results"][0]["action"] == "invoice_send"


def test_results_are_capped_and_truncated_flag_is_set(client, admin_user, employee, settings):
    """境界値: 上限件数を超えた分は切り捨て、truncated=Trueで呼び出し元に伝える。"""
    from apps.compliance import views as compliance_views

    original_limit = compliance_views.AUDIT_LOG_LIST_LIMIT
    compliance_views.AUDIT_LOG_LIST_LIMIT = 3
    try:
        for _ in range(5):
            _seed(admin_user, "employee_update", "User", employee.id)

        client.force_login(admin_user)
        res = client.get(reverse("admin-audit-logs"))
        body = res.json()
        assert body["total_count"] == 5
        assert len(body["results"]) == 3
        assert body["truncated"] is True
    finally:
        compliance_views.AUDIT_LOG_LIST_LIMIT = original_limit


def test_results_ordered_most_recent_first(client, admin_user, employee):
    first = _seed(admin_user, "employee_update", "User", employee.id)
    AuditLog.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(minutes=5))
    second = _seed(admin_user, "employee_update", "User", employee.id)

    client.force_login(admin_user)
    res = client.get(reverse("admin-audit-logs"))
    ids = [row["id"] for row in res.json()["results"]]
    assert ids == [second.id, first.id]
