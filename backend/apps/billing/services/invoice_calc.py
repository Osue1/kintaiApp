"""請求金額（小計）の算出（設計書 第8.2章）。

単価タイプごとの計算式のみを純関数として持つ。単価の解決（履歴からの引き当て）は
apps.contractors.services.rates.resolve_rate が担う。
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def calc_subtotal_hourly(hours: Decimal, hourly_rate: Decimal) -> Decimal:
    return (hours * hourly_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calc_subtotal_daily(days: Decimal, daily_rate: Decimal) -> Decimal:
    return (days * daily_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calc_subtotal_fixed(fixed_amount: Decimal) -> Decimal:
    return fixed_amount
