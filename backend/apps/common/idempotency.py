"""`Idempotency-Key` ヘッダによる二重実行防止（打刻・請求書生成など）。

クライアントが `Idempotency-Key` ヘッダを付けてリクエストした場合、同一ユーザー・同一
エンドポイントで同じキーが再送されても実処理を再実行せず、前回のレスポンスをそのまま
返す。ヘッダが無ければ従来通り毎回処理する（既存クライアントへの後方互換）。
"""
from collections.abc import Callable
from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response

from apps.common.models import IdempotencyKey

HEADER_NAME = "HTTP_IDEMPOTENCY_KEY"

# 再送検知のためだけの短命データなので、実務上あり得る再送の猶予（数日）を過ぎたら
# 保持し続ける意味がない。長く残すほど response_body（JSONField）が無制限に肥大化する。
IDEMPOTENCY_KEY_RETENTION_DAYS = 7


def with_idempotency(request, endpoint: str, handler: Callable[[], Response]) -> Response:
    """`handler` を呼ぶ前に `Idempotency-Key` の再送をチェックし、あれば前回のレスポンスを返す。
    無ければ `handler()` を実行し、キーが指定されていれば結果を記録してから返す。
    """
    key = request.META.get(HEADER_NAME)
    if not key:
        return handler()

    user = getattr(request, "user", None)
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None

    existing = IdempotencyKey.objects.filter(key=key, endpoint=endpoint, user=user).first()
    if existing is not None:
        return Response(existing.response_body, status=existing.response_status)

    response = handler()
    # レンダリング前でも .data / .status_code は参照できる（DRF Response）
    IdempotencyKey.objects.get_or_create(
        key=key,
        endpoint=endpoint,
        user=user,
        defaults={"response_status": response.status_code, "response_body": response.data},
    )
    return response


def delete_expired_idempotency_keys(retention_days: int = IDEMPOTENCY_KEY_RETENTION_DAYS) -> int:
    """保持期限を過ぎた IdempotencyKey を削除し、削除件数を返す（日次バッチ想定）。"""
    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted_count, _ = IdempotencyKey.objects.filter(created_at__lt=cutoff).delete()
    return deleted_count
