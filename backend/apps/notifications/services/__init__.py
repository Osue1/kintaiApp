"""通知チャネルの抽象。初期は in-app のみ有効にする（設計書 第11.1章）。

notify(user, category, title, body, link) → 有効なチャネルすべてに配信。
メール／Slack は将来拡張として NotificationChannel を増やすだけで足りるようにする。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from django.utils import timezone

from apps.notifications.models import Notification, NotificationCategory


class NotificationChannel(Protocol):
    def send(self, user, category: str, title: str, body: str, link: str) -> None: ...


class InAppChannel:
    def send(self, user, category: str, title: str, body: str, link: str) -> None:
        Notification.objects.create(user=user, category=category, title=title, body=body, link=link)


CHANNELS: tuple[NotificationChannel, ...] = (InAppChannel(),)


def notify(user, category: NotificationCategory | str, title: str, body: str = "", link: str = "") -> None:
    for channel in CHANNELS:
        channel.send(user, category, title, body, link)


# マイページの通知一覧ダイアログが選べる最大期間（過去90日、MyPageView.vue参照）より
# 十分長く取り、UIから閲覧できる範囲のデータが裏で消えていることのないようにする。
# 既読・未読に関わらず一律で削除する（未読のまま1年放置された通知は実質見られておらず、
# 読み既読フラグだけで保持要否を分けるとロジックが複雑になる割に得るものが小さいため）。
NOTIFICATION_RETENTION_DAYS = 365


def delete_old_notifications(retention_days: int = NOTIFICATION_RETENTION_DAYS) -> int:
    """保持期限を過ぎた Notification を削除し、削除件数を返す（日次バッチ想定）。"""
    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted_count, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
    return deleted_count
