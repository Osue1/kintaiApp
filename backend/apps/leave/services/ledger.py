"""年次有給休暇管理簿の組み立て（設計書 第6.3章「法定帳簿」・第12.2章 保存期間3年）。

労基則24条の7が求める記載事項は「時季・日数・基準日」。付与ロット（基準日）ごとに、
そのロットから消化された休暇（時季・日数）を紐付けて一覧化する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone

from apps.leave.models import PaidLeaveGrant


@dataclass
class ConsumptionEntry:
    date_label: str
    days: Decimal
    leave_type_name: str


@dataclass
class GrantLedgerRow:
    granted_on: str
    days: Decimal
    expires_on: str
    consumed: Decimal
    remaining: Decimal
    is_expired: bool
    consumptions: list[ConsumptionEntry] = field(default_factory=list)


def build_ledger(user) -> list[GrantLedgerRow]:
    today = timezone.localdate()
    grants = PaidLeaveGrant.objects.filter(user=user).order_by("granted_on").prefetch_related(
        "consumptions__leave_request__leave_type"
    )
    rows: list[GrantLedgerRow] = []
    for grant in grants:
        consumptions = []
        consumed_total = Decimal("0")
        for c in grant.consumptions.all().order_by("leave_request__start_date"):
            lr = c.leave_request
            date_label = (
                str(lr.start_date) if lr.start_date == lr.end_date else f"{lr.start_date}〜{lr.end_date}"
            )
            consumptions.append(
                ConsumptionEntry(date_label=date_label, days=c.days, leave_type_name=lr.leave_type.name)
            )
            consumed_total += c.days

        rows.append(
            GrantLedgerRow(
                granted_on=str(grant.granted_on),
                days=grant.days,
                expires_on=str(grant.expires_on),
                consumed=consumed_total,
                remaining=grant.days - consumed_total,
                is_expired=grant.expires_on < today,
                consumptions=consumptions,
            )
        )
    return rows
