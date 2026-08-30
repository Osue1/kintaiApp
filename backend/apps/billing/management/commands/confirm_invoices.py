"""仕入明細書の確認期限を過ぎた分を「みなし確認」にするバッチ（設計書 第8.5章）。

ローカル/デモでは cron を組む代わりに手動で実行する（grant_paid_leave と同様の運用）。
"""
from django.core.management.base import BaseCommand

from apps.billing.services.confirmation import deem_overdue_confirmations


class Command(BaseCommand):
    help = "確認期限を過ぎても未確認の仕入明細書を「みなし確認」にする"

    def handle(self, *args, **options) -> None:
        updated = deem_overdue_confirmations()
        for confirmation in updated:
            self.stdout.write(f"みなし確認: {confirmation.invoice.invoice_no}")
        self.stdout.write(self.style.SUCCESS(f"{len(updated)}件をみなし確認にしました"))
