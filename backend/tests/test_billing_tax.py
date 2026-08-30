"""消費税・源泉徴収・免税事業者控除率の計算（設計書 第8.3章・第8.4章・第13.1章の境界値）。"""
from datetime import date
from decimal import Decimal

import pytest

from apps.billing.services.tax import (
    ExemptDeductionRateRow,
    TaxRateRow,
    WithholdingRuleRow,
    calc_tax_amount,
    calc_withholding_amount,
    resolve_exempt_deduction_rate,
    resolve_tax_rate,
    round_amount,
)

RULE = WithholdingRuleRow(
    threshold_amount=Decimal("1000000"),
    rate_below_percent=Decimal("10.21"),
    rate_above_percent=Decimal("20.42"),
    effective_from=date(2013, 1, 1),
)


def test_withholding_exactly_at_threshold_uses_lower_rate_only():
    """課税標準1,000,000円ちょうど（設計書 13.1 境界値）。"""
    amount = calc_withholding_amount(Decimal("1000000"), RULE)
    assert amount == Decimal("102100")  # 1,000,000 * 10.21%


def test_withholding_just_above_threshold_splits_rates():
    amount = calc_withholding_amount(Decimal("1000001"), RULE)
    # 1,000,000*10.21% + 1*20.42% = 102100 + 0.2042 → 切り捨てで102100
    assert amount == Decimal("102100")


def test_withholding_well_above_threshold():
    amount = calc_withholding_amount(Decimal("1500000"), RULE)
    # 102100 + 500000*20.42% = 102100 + 102100 = 204200
    assert amount == Decimal("204200")


def test_withholding_rounds_down_fractional_yen():
    """端数0.5円は切り捨てる（1円未満切捨て、設計書 第8.3章）。"""
    rule = WithholdingRuleRow(
        threshold_amount=Decimal("1000000"),
        rate_below_percent=Decimal("10.005"),
        rate_above_percent=Decimal("20.42"),
        effective_from=date(2013, 1, 1),
    )
    # 5 * 10.005% = 0.50025 → 切り捨てで 0円
    assert calc_withholding_amount(Decimal("5"), rule) == Decimal("0")


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("floor", Decimal("100")), ("round", Decimal("101")), ("ceil", Decimal("101"))],
)
def test_round_amount_modes(mode, expected):
    assert round_amount(Decimal("100.5"), mode) == expected


def test_mixed_standard_and_reduced_rate_invoice():
    """10%と8%が混在する請求は、区分ごとに1回だけ端数処理する（インボイス制度の要件）。"""
    rates = (
        TaxRateRow("standard", Decimal("10.00"), date(2019, 10, 1)),
        TaxRateRow("reduced", Decimal("8.00"), date(2019, 10, 1)),
    )
    standard_rate = resolve_tax_rate(rates, "standard", date(2026, 8, 1))
    reduced_rate = resolve_tax_rate(rates, "reduced", date(2026, 8, 1))
    standard_tax = calc_tax_amount(Decimal("10000"), standard_rate, "floor")
    reduced_tax = calc_tax_amount(Decimal("10000"), reduced_rate, "floor")
    assert standard_tax == Decimal("1000")
    assert reduced_tax == Decimal("800")


def test_exempt_deduction_rate_straddles_2026_10_01_boundary():
    """免税事業者の控除率が 2026-09-30 と 2026-10-01 をまたぐ請求（設計書 13.1 境界値）。"""
    rows = (
        ExemptDeductionRateRow(Decimal("80.00"), date(2023, 10, 1), date(2026, 9, 30)),
        ExemptDeductionRateRow(Decimal("50.00"), date(2026, 10, 1), date(2029, 9, 30)),
        ExemptDeductionRateRow(Decimal("0.00"), date(2029, 10, 1), None),
    )
    assert resolve_exempt_deduction_rate(rows, date(2026, 9, 30)) == Decimal("80.00")
    assert resolve_exempt_deduction_rate(rows, date(2026, 10, 1)) == Decimal("50.00")
    assert resolve_exempt_deduction_rate(rows, date(2029, 10, 1)) == Decimal("0.00")


def test_exempt_deduction_rate_with_no_match_defaults_to_zero():
    assert resolve_exempt_deduction_rate((), date(2020, 1, 1)) == Decimal("0")
