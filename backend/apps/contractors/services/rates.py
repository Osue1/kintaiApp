"""単価解決ロジック（設計書 第4.1章 ③・第8.2章）。

「稼働日時点で有効な単価」を適用開始日で解決する。過去分の再発行でも当時の単価が
再現されるよう、単価は履歴として持ち、値を上書きしない。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RateHistoryRow:
    id: int
    rate_type: str
    rate_amount: Decimal
    effective_from: date
    effective_to: date | None = None


def resolve_rate(rates: tuple[RateHistoryRow, ...], on_date: date) -> RateHistoryRow | None:
    applicable = [
        r
        for r in rates
        if r.effective_from <= on_date and (r.effective_to is None or on_date <= r.effective_to)
    ]
    if not applicable:
        return None
    return max(applicable, key=lambda r: r.effective_from)
