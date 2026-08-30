"""消費税・源泉徴収・免税事業者控除率の計算（設計書 第8.3章・第8.4章）。

金額はすべて Decimal で扱う。float を経由させない（設計書 第13.1章）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal


class RoundingMode:
    FLOOR = "floor"
    ROUND = "round"
    CEIL = "ceil"


_ROUNDING = {
    RoundingMode.FLOOR: ROUND_FLOOR,
    RoundingMode.ROUND: ROUND_HALF_UP,
    RoundingMode.CEIL: ROUND_CEILING,
}


def round_amount(value: Decimal, mode: str) -> Decimal:
    return value.quantize(Decimal("1"), rounding=_ROUNDING[mode])


@dataclass(frozen=True, slots=True)
class TaxRateRow:
    category: str
    rate_percent: Decimal
    effective_from: date
    effective_to: date | None = None


def resolve_tax_rate(rates: tuple[TaxRateRow, ...], category: str, on_date: date) -> Decimal:
    applicable = [
        r
        for r in rates
        if r.category == category
        and r.effective_from <= on_date
        and (r.effective_to is None or on_date <= r.effective_to)
    ]
    if not applicable:
        raise ValueError(f"{on_date} 時点の税率区分「{category}」が見つかりません。")
    return max(applicable, key=lambda r: r.effective_from).rate_percent


def calc_tax_amount(subtotal: Decimal, rate_percent: Decimal, rounding_mode: str) -> Decimal:
    """税率区分ごとに1回だけ端数処理する（インボイス制度の要件、設計書 第8.3章）。"""
    return round_amount(subtotal * rate_percent / Decimal("100"), rounding_mode)


@dataclass(frozen=True, slots=True)
class WithholdingRuleRow:
    threshold_amount: Decimal
    rate_below_percent: Decimal
    rate_above_percent: Decimal
    effective_from: date
    effective_to: date | None = None


def resolve_withholding_rule(rules: tuple[WithholdingRuleRow, ...], on_date: date) -> WithholdingRuleRow:
    applicable = [
        r
        for r in rules
        if r.effective_from <= on_date and (r.effective_to is None or on_date <= r.effective_to)
    ]
    if not applicable:
        raise ValueError(f"{on_date} 時点の源泉徴収税率が見つかりません。")
    return max(applicable, key=lambda r: r.effective_from)


def calc_withholding_amount(taxable_base: Decimal, rule: WithholdingRuleRow) -> Decimal:
    """報酬 ≤ 閾値 → 報酬×税率／超過分は超過税率。1円未満切り捨て（設計書 第8.3章）。

    課税標準は「請求書上で報酬と消費税が明確に区分されていれば税抜額」（同章）。
    """
    if taxable_base <= rule.threshold_amount:
        amount = taxable_base * rule.rate_below_percent / Decimal("100")
    else:
        amount = (
            rule.threshold_amount * rule.rate_below_percent / Decimal("100")
            + (taxable_base - rule.threshold_amount) * rule.rate_above_percent / Decimal("100")
        )
    return round_amount(amount, RoundingMode.FLOOR)


@dataclass(frozen=True, slots=True)
class ExemptDeductionRateRow:
    deduction_percent: Decimal
    effective_from: date
    effective_to: date | None = None


def resolve_exempt_deduction_rate(rows: tuple[ExemptDeductionRateRow, ...], on_date: date) -> Decimal:
    """2026-10-01 の制度変更をまたぐ請求にも対応する（設計書 第8.4章）。該当なしは0%。"""
    applicable = [
        r
        for r in rows
        if r.effective_from <= on_date and (r.effective_to is None or on_date <= r.effective_to)
    ]
    if not applicable:
        return Decimal("0")
    return max(applicable, key=lambda r: r.effective_from).deduction_percent
