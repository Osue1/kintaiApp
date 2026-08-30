"""保持期限を過ぎたデータの削除バッチ（IdempotencyKey・Notification・任意でAuditLog）。

対象:
- IdempotencyKey: 二重実行防止のためだけの短命データ（既定7日）。放置すると
  response_body（JSONField）が無制限に肥大化する。
- Notification: マイページの通知一覧が閲覧できる最大期間（過去90日）より十分長い
  既定365日。
- AuditLog: 業務記録としての性質上、既定では対象外（--include-audit-log を明示指定
  した場合のみ、既定1825日=5年で削除する。誤って監査証跡を消してしまう事故を避けるため）。

ローカル/デモでは cron を組む代わりに手動で実行する（grant_paid_leave 等と同様の運用）。
"""
from django.core.management.base import BaseCommand

from apps.common.audit import AUDIT_LOG_RETENTION_DAYS, delete_old_audit_logs
from apps.common.idempotency import IDEMPOTENCY_KEY_RETENTION_DAYS, delete_expired_idempotency_keys
from apps.notifications.services import NOTIFICATION_RETENTION_DAYS, delete_old_notifications


class Command(BaseCommand):
    help = "保持期限を過ぎたIdempotencyKey/Notification（任意でAuditLog）を削除する"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--include-audit-log",
            action="store_true",
            help="AuditLogも削除対象に含める（既定では対象外。監査証跡のため明示指定が必要）",
        )

    def handle(self, *args, **options) -> None:
        idempotency_deleted = delete_expired_idempotency_keys()
        self.stdout.write(
            f"IdempotencyKey: {idempotency_deleted}件削除（保持期限 {IDEMPOTENCY_KEY_RETENTION_DAYS}日）"
        )

        notification_deleted = delete_old_notifications()
        self.stdout.write(
            f"Notification: {notification_deleted}件削除（保持期限 {NOTIFICATION_RETENTION_DAYS}日）"
        )

        if options["include_audit_log"]:
            audit_deleted = delete_old_audit_logs()
            self.stdout.write(
                f"AuditLog: {audit_deleted}件削除（保持期限 {AUDIT_LOG_RETENTION_DAYS}日）"
            )
        else:
            self.stdout.write("AuditLog: スキップ（--include-audit-log を指定すると削除対象になります）")

        self.stdout.write(self.style.SUCCESS("保持期限切れデータの削除バッチが完了しました"))
