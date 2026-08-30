"""仕入明細書としての確認記録フロー（設計書 第8.5章）。

インボイス制度の「仕入明細書等」方式では、発行側（自社）が明細を送付し、相手方（外注先）が
一定期間内に異議を述べなければ内容を確認したものとみなす、という運用が一般的。ここでは送付時に
確認期限を設定し、期限を過ぎても異議（明示的な確認）が記録されなければ「みなし確認」として扱う。

確認期間は日数だけを純関数として切り出し、実際の日付判定はDBに依存しない形でテストする。
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceConfirmation

# 確認期限（送付日から何日で「みなし確認」とするか）。設計書に明示の日数がないため、
# インボイス制度の実務慣行を踏まえた妥当な既定値として設定する。会社ごとに変える必要が
# 出てきた場合は Company モデルに設定項目を追加して差し替える。
CONFIRM_PERIOD_DAYS = 14


@dataclass(frozen=True)
class ConfirmationState:
    """判定に必要な最小限のフィールドだけを持つ、DBに依存しない状態表現。"""

    notified_at: datetime | None
    confirm_deadline: date | None
    confirmed_at: datetime | None


def should_deem_confirmed(state: ConfirmationState, as_of: date) -> bool:
    """通知済み・未確認・確認期限を過ぎている場合に「みなし確認」とすべきかを判定する。"""
    if state.notified_at is None or state.confirmed_at is not None or state.confirm_deadline is None:
        return False
    return as_of > state.confirm_deadline


def notify_for_confirmation(invoice: Invoice) -> InvoiceConfirmation:
    """請求書（仕入明細書）を送付した際に、確認記録の起点を作る／更新する。"""
    now = timezone.now()
    deadline = _add_days(timezone.localdate(), CONFIRM_PERIOD_DAYS)
    confirmation, _ = InvoiceConfirmation.objects.update_or_create(
        invoice=invoice,
        defaults={"notified_at": now, "confirm_deadline": deadline},
    )
    return confirmation


def confirm_manually(confirmation: InvoiceConfirmation) -> InvoiceConfirmation:
    """管理者が外注先からの確認（電話・メール等）を受けて手動で確認済みにする。"""
    confirmation.confirmed_at = timezone.now()
    confirmation.confirm_method = "manual"
    confirmation.save(update_fields=["confirmed_at", "confirm_method"])
    return confirmation


@transaction.atomic
def deem_overdue_confirmations(as_of: date | None = None) -> list[InvoiceConfirmation]:
    """確認期限を過ぎても未確認のものを「みなし確認」にする（毎日のバッチ想定）。"""
    as_of = as_of or timezone.localdate()
    overdue = InvoiceConfirmation.objects.filter(
        notified_at__isnull=False, confirmed_at__isnull=True, confirm_deadline__lt=as_of
    )
    updated: list[InvoiceConfirmation] = []
    for confirmation in overdue:
        confirmation.confirmed_at = timezone.now()
        confirmation.confirm_method = "deemed_after_deadline"
        confirmation.save(update_fields=["confirmed_at", "confirm_method"])
        updated.append(confirmation)
    return updated


def _add_days(d: date, days: int) -> date:
    return d + timedelta(days=days)
