from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """全テーブル共通の created_at / updated_at。"""

    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        abstract = True


class IdempotencyKey(models.Model):
    """`Idempotency-Key` ヘッダによる二重実行防止の記録（打刻・請求書生成など）。

    同一ユーザー・同一エンドポイント・同一キーでのリクエストは、実処理を再実行せず
    前回のレスポンスをそのまま返す。ネットワーク再送やダブルクリックによる意図しない
    二重処理（例: 打刻の二重登録、請求書の重複生成）を防ぐ。
    """

    key = models.CharField("Idempotency-Key", max_length=255)
    endpoint = models.CharField("エンドポイント", max_length=100)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    response_status = models.PositiveSmallIntegerField("レスポンスステータス")
    response_body = models.JSONField("レスポンスボディ", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "Idempotencyキー"
        constraints = [
            models.UniqueConstraint(fields=["key", "endpoint", "user"], name="unique_idempotency_key_per_endpoint_user")
        ]

    def __str__(self) -> str:
        return f"{self.endpoint}:{self.key}"
