"""IdempotencyKey・Notification・AuditLogの保持期限切れデータ削除（設計上の欠陥の修正確認）。"""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.models import AuditLog
from apps.common.audit import delete_old_audit_logs, record_audit
from apps.common.idempotency import delete_expired_idempotency_keys
from apps.common.models import IdempotencyKey
from apps.notifications.models import Notification
from apps.notifications.services import delete_old_notifications, notify

pytestmark = pytest.mark.django_db


def _backdate(queryset, pk, days: int) -> None:
    queryset.filter(pk=pk).update(created_at=timezone.now() - timedelta(days=days))


# --- IdempotencyKey ---

def test_delete_expired_idempotency_keys_removes_only_records_past_retention(admin_user):
    fresh = IdempotencyKey.objects.create(key="fresh", endpoint="ep", user=admin_user, response_status=200)
    old = IdempotencyKey.objects.create(key="old", endpoint="ep", user=admin_user, response_status=200)
    _backdate(IdempotencyKey.objects, old.pk, days=8)

    deleted = delete_expired_idempotency_keys(retention_days=7)

    assert deleted == 1
    assert IdempotencyKey.objects.filter(pk=fresh.pk).exists()
    assert not IdempotencyKey.objects.filter(pk=old.pk).exists()


def test_delete_expired_idempotency_keys_boundary_just_within_retention_is_kept(admin_user):
    """境界値: 保持期限にわずかに満たない（6日23時間経過）ものはまだ削除しない。"""
    boundary = IdempotencyKey.objects.create(key="boundary", endpoint="ep", user=admin_user, response_status=200)
    IdempotencyKey.objects.filter(pk=boundary.pk).update(
        created_at=timezone.now() - timedelta(days=6, hours=23)
    )

    deleted = delete_expired_idempotency_keys(retention_days=7)

    assert deleted == 0
    assert IdempotencyKey.objects.filter(pk=boundary.pk).exists()


# --- Notification ---

def test_delete_old_notifications_removes_regardless_of_read_status(employee):
    notify(employee, "info", "最近の通知")
    unread_old = Notification.objects.create(user=employee, category="info", title="古い未読通知")
    read_old = Notification.objects.create(user=employee, category="info", title="古い既読通知", read_at=timezone.now())
    _backdate(Notification.objects, unread_old.pk, days=366)
    _backdate(Notification.objects, read_old.pk, days=400)

    deleted = delete_old_notifications(retention_days=365)

    assert deleted == 2
    assert Notification.objects.filter(title="最近の通知").exists()
    assert not Notification.objects.filter(pk__in=[unread_old.pk, read_old.pk]).exists()


# --- AuditLog ---

def test_delete_old_audit_logs_removes_only_records_past_retention(admin_user):
    request = RequestFactory().post("/api/v1/whatever")
    request.user = admin_user
    record_audit(request, "employee_update", "User", admin_user.id)
    old_log = AuditLog.objects.order_by("id").first()
    _backdate(AuditLog.objects, old_log.pk, days=1826)
    record_audit(request, "employee_update", "User", admin_user.id)  # 新しい方は残るはず

    deleted = delete_old_audit_logs(retention_days=1825)

    assert deleted == 1
    assert not AuditLog.objects.filter(pk=old_log.pk).exists()
    assert AuditLog.objects.count() == 1


# --- 管理コマンド ---

def test_cleanup_command_deletes_idempotency_and_notifications_but_not_audit_log_by_default(
    admin_user, employee
):
    old_key = IdempotencyKey.objects.create(key="old", endpoint="ep", user=admin_user, response_status=200)
    _backdate(IdempotencyKey.objects, old_key.pk, days=8)

    old_notification = Notification.objects.create(user=employee, category="info", title="古い通知")
    _backdate(Notification.objects, old_notification.pk, days=400)

    request = RequestFactory().post("/api/v1/whatever")
    request.user = admin_user
    record_audit(request, "employee_update", "User", admin_user.id)
    old_audit = AuditLog.objects.order_by("id").first()
    _backdate(AuditLog.objects, old_audit.pk, days=1826)

    call_command("cleanup_expired_records")

    assert not IdempotencyKey.objects.filter(pk=old_key.pk).exists()
    assert not Notification.objects.filter(pk=old_notification.pk).exists()
    # --include-audit-log を指定しない限り、監査ログは既定では対象外
    assert AuditLog.objects.filter(pk=old_audit.pk).exists()


def test_cleanup_command_with_include_audit_log_flag_also_deletes_old_audit_logs(admin_user):
    request = RequestFactory().post("/api/v1/whatever")
    request.user = admin_user
    record_audit(request, "employee_update", "User", admin_user.id)
    old_audit = AuditLog.objects.order_by("id").first()
    _backdate(AuditLog.objects, old_audit.pk, days=1826)

    call_command("cleanup_expired_records", "--include-audit-log")

    assert not AuditLog.objects.filter(pk=old_audit.pk).exists()
