from django.conf import settings
from django.db import models


class NotificationCategory(models.TextChoices):
    APPROVAL = "approval", "承認"
    REMINDER = "reminder", "リマインド"
    INFO = "info", "お知らせ"


class Notification(models.Model):
    """マイページ通知。仕様書どおり初期は in-app のみ（設計書 第11.1章 InAppChannel）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="宛先", on_delete=models.CASCADE, related_name="notifications"
    )
    category = models.CharField("種別", max_length=20, choices=NotificationCategory.choices)
    title = models.CharField("タイトル", max_length=120)
    body = models.CharField("本文", max_length=300, blank=True)
    link = models.CharField("リンク", max_length=200, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    read_at = models.DateTimeField("既読日時", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "通知"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} {self.title}"
