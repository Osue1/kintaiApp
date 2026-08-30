"""通知の個別既読・期間指定履歴のテスト。"""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


def test_mark_one_notification_read(client, employee):
    n = Notification.objects.create(user=employee, category="info", title="テスト通知", body="本文")
    client.force_login(employee)

    res = client.post(reverse("notifications-read-one", args=[n.id]))
    assert res.status_code == 200
    assert res.json()["read"] is True

    n.refresh_from_db()
    assert n.read_at is not None


def test_cannot_mark_other_users_notification_read(client, employee, admin_user):
    n = Notification.objects.create(user=admin_user, category="info", title="他人の通知", body="")
    client.force_login(employee)

    res = client.post(reverse("notifications-read-one", args=[n.id]))
    assert res.status_code == 404


def test_list_without_days_returns_recent_only(client, employee):
    for i in range(25):
        Notification.objects.create(user=employee, category="info", title=f"通知{i}", body="")
    client.force_login(employee)

    res = client.get(reverse("notifications-list"))
    assert res.status_code == 200
    assert len(res.json()) == 20


def test_list_with_days_returns_history_within_window(client, employee):
    old = Notification.objects.create(user=employee, category="info", title="古い通知", body="")
    Notification.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=100))
    Notification.objects.create(user=employee, category="info", title="最近の通知", body="")
    client.force_login(employee)

    res = client.get(reverse("notifications-list"), {"days": 30})
    titles = [n["title"] for n in res.json()]
    assert "最近の通知" in titles
    assert "古い通知" not in titles
