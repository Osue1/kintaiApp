"""監査ログ記録ヘルパー（設計書 第12.1章「承認・打刻修正・マスタ変更・請求書発行を記録する」）。

view層から1行で呼べるようにする薄いラッパー。record自体はAuditLogモデルへの素直なcreateで、
書き込み失敗が本処理を巻き込まないよう例外は握りつぶしてログに残すのみとする
（監査ログの欠落より、承認・打刻修正などの本処理が失敗する方が実害が大きいため）。
"""
import logging
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import AuditLog

logger = logging.getLogger(__name__)

# 監査ログは労務・税務関連の記録と紐づく可能性があり、IdempotencyKeyやNotificationのような
# 単なる運用上の一時データとは性質が異なる。自動削除は業務記録としての保存義務（労基法・
# 税法関連の帳簿書類は概ね5〜7年保存が実務慣行）を踏まえ、無期限に肥大化させないための
# 「十分に長い」既定値として5年（1825日）を設定する。実運用では会社の記録保存方針に
# 合わせて調整すること。IdempotencyKey/Notificationと違い自動バッチには含めず、
# cleanup_expired_records コマンドの --include-audit-log を明示指定した場合のみ対象にする
# （監査証跡を誤って自動削除してしまう事故を避けるため）。
AUDIT_LOG_RETENTION_DAYS = 1825


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_audit(
    request,
    action: str,
    target_type: str,
    target_id: int | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """request（DRFのRequest/HttpRequest）から操作者・IP・User-Agentを取り、監査ログを1件書き込む。"""
    try:
        actor = getattr(request, "user", None)
        if actor is not None and not getattr(actor, "is_authenticated", False):
            actor = None
        AuditLog.objects.create(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            ip=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
        )
    except Exception:  # noqa: BLE001 - 監査ログの失敗で本処理を止めない
        logger.exception("監査ログの記録に失敗しました: action=%s target_type=%s target_id=%s", action, target_type, target_id)


def delete_old_audit_logs(retention_days: int = AUDIT_LOG_RETENTION_DAYS) -> int:
    """保持期限を過ぎた AuditLog を削除し、削除件数を返す。

    業務記録としての性質上、日次バッチには自動で含めない（cleanup_expired_records の
    --include-audit-log を明示指定した場合のみ呼ばれる）。呼ぶ場合も retention_days は
    十分に長い値にとどめること。
    """
    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted_count, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()
    return deleted_count
