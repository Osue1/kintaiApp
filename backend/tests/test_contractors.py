"""外注の単価解決・締め期間算出（設計書 第4.1章③・第8.1章・第8.2章）。"""
from datetime import date
from decimal import Decimal

from apps.billing.services.invoice_calc import (
    calc_subtotal_daily,
    calc_subtotal_fixed,
    calc_subtotal_hourly,
)
from apps.contractors.services.closing import resolve_closing_period
from apps.contractors.services.rates import RateHistoryRow, resolve_rate


def test_resolve_rate_picks_the_one_effective_on_date():
    rates = (
        RateHistoryRow(1, "hourly", Decimal("4000"), date(2025, 1, 1), date(2025, 12, 31)),
        RateHistoryRow(2, "hourly", Decimal("4500"), date(2026, 1, 1), None),
    )
    assert resolve_rate(rates, date(2025, 6, 1)).rate_amount == Decimal("4000")
    assert resolve_rate(rates, date(2026, 1, 1)).rate_amount == Decimal("4500")
    assert resolve_rate(rates, date(2030, 1, 1)).rate_amount == Decimal("4500")


def test_resolve_rate_none_before_any_history():
    rates = (RateHistoryRow(1, "hourly", Decimal("4000"), date(2025, 1, 1), None),)
    assert resolve_rate(rates, date(2024, 12, 31)) is None


def test_rate_change_mid_closing_period_is_captured_by_effective_dates():
    """単価改定が締め期間内にある月（設計書 13.1 境界値）— 稼働日ごとに当時の単価で解決する。"""
    rates = (
        RateHistoryRow(1, "daily", Decimal("25000"), date(2026, 1, 1), date(2026, 1, 15)),
        RateHistoryRow(2, "daily", Decimal("28000"), date(2026, 1, 16), None),
    )
    assert resolve_rate(rates, date(2026, 1, 10)).rate_amount == Decimal("25000")
    assert resolve_rate(rates, date(2026, 1, 20)).rate_amount == Decimal("28000")


def test_closing_period_treats_31_as_month_end():
    period = resolve_closing_period(
        closing_day=31, payment_month_offset=1, payment_day=10, for_year=2026, for_month=2
    )
    assert period.period_end == date(2026, 2, 28)
    assert period.period_start == date(2026, 2, 1)  # 前月(1月)の締め日=月末(1/31)の翌日


def test_closing_period_payment_due_rolls_forward_from_weekend():
    # 2026-04-10 は金曜、2026-05-10 は日曜 → 前営業日(5/8金)へ繰上げ
    period = resolve_closing_period(
        closing_day=31, payment_month_offset=1, payment_day=10, for_year=2026, for_month=4
    )
    assert period.payment_due_date.weekday() < 5


def test_subtotal_calculations_use_decimal_precision():
    assert calc_subtotal_hourly(Decimal("62.5"), Decimal("4500")) == Decimal("281250")
    assert calc_subtotal_daily(Decimal("14"), Decimal("28000")) == Decimal("392000")
    assert calc_subtotal_fixed(Decimal("350000")) == Decimal("350000")
