"""締め日到来分の請求書を一括生成する（設計書 第8.6章）。

単価解決・締め期間算出・消費税額・源泉徴収額は、それぞれ専用の純関数へ委譲する。
ここでは ORM から値オブジェクトへ変換し、保存するオーケストレーションだけを行う。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Company
from apps.billing.models import (
    ExemptDeductionRate,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    TaxRate,
    WithholdingRule,
)
from apps.billing.services.invoice_calc import (
    calc_subtotal_daily,
    calc_subtotal_fixed,
    calc_subtotal_hourly,
)
from apps.billing.services.tax import (
    ExemptDeductionRateRow,
    TaxRateRow,
    WithholdingRuleRow,
    calc_tax_amount,
    calc_withholding_amount,
    resolve_exempt_deduction_rate,
    resolve_tax_rate,
    resolve_withholding_rule,
)
from apps.contractors.models import Contractor, ContractorWorkRecord
from apps.contractors.models import TaxCategory as ContractorTaxCategory
from apps.contractors.services.rates import RateHistoryRow, resolve_rate


@dataclass
class GenerationResult:
    created: list[Invoice]
    skipped_no_record: list[Contractor]
    already_exists: list[Contractor]


def _tax_rate_rows() -> tuple[TaxRateRow, ...]:
    return tuple(
        TaxRateRow(r.category, r.rate_percent, r.effective_from, r.effective_to)
        for r in TaxRate.objects.all()
    )


def _exempt_rows() -> tuple[ExemptDeductionRateRow, ...]:
    return tuple(
        ExemptDeductionRateRow(r.deduction_percent, r.effective_from, r.effective_to)
        for r in ExemptDeductionRate.objects.all()
    )


def _withholding_rows() -> tuple[WithholdingRuleRow, ...]:
    return tuple(
        WithholdingRuleRow(r.threshold_amount, r.rate_below_percent, r.rate_above_percent, r.effective_from, r.effective_to)
        for r in WithholdingRule.objects.all()
    )


@transaction.atomic
def generate_invoices_for_month(year_month: str, created_by=None) -> GenerationResult:
    company = Company.get_solo()
    period_end = _last_day_of_period(year_month)
    tax_rates = _tax_rate_rows()
    exempt_rows = _exempt_rows()
    withholding_rows = _withholding_rows()

    created: list[Invoice] = []
    skipped_no_record: list[Contractor] = []
    already_exists: list[Contractor] = []

    for contractor in Contractor.objects.filter(is_active=True).prefetch_related("rates"):
        # ここでの「存在チェック→作成」自体は競合状態に対して無力な点に注意。
        # 「一括生成」ボタンの連打や、複数管理者による同時実行が起きた場合、両方の
        # トランザクションがこのチェックを素通りしてから作成に進む可能性がある
        # （チェックと作成の間に別トランザクションが割り込む、典型的な check-then-act 競合）。
        # そのためこのチェックは「無駄な生成を早めに省くための最適化」に過ぎず、
        # 真の二重発行防止は Invoice.Meta の部分一意インデックス（uniq_active_invoice_
        # per_contractor_period）が担う。実際に競合が起きて DB 制約に弾かれた場合は
        # 下の except IntegrityError で拾い、already_exists 扱いにフォールバックする。
        if Invoice.objects.filter(contractor=contractor, period_end__year=period_end.year, period_end__month=period_end.month).exclude(status=InvoiceStatus.VOID).exists():
            already_exists.append(contractor)
            continue

        record = ContractorWorkRecord.objects.filter(contractor=contractor, year_month=year_month).first()
        rate_rows = tuple(
            RateHistoryRow(r.id, r.rate_type, r.rate_amount, r.effective_from, r.effective_to)
            for r in contractor.rates.all()
        )
        rate = resolve_rate(rate_rows, period_end)
        if rate is None:
            skipped_no_record.append(contractor)
            continue

        subtotal = _calc_subtotal(rate.rate_type, rate.rate_amount, record)
        if subtotal is None:
            skipped_no_record.append(contractor)
            continue

        tax_category = "exempt" if contractor.tax_category == ContractorTaxCategory.EXEMPT else "standard"
        rate_percent = resolve_tax_rate(tax_rates, tax_category, period_end)
        tax_amount = calc_tax_amount(subtotal, rate_percent, company.rounding_mode)

        exempt_percent = None
        if contractor.tax_category == ContractorTaxCategory.EXEMPT:
            exempt_percent = resolve_exempt_deduction_rate(exempt_rows, period_end)

        withholding_amount = Decimal("0")
        if contractor.withholding_target:
            rule = resolve_withholding_rule(withholding_rows, period_end)
            withholding_amount = calc_withholding_amount(subtotal, rule)

        payable = subtotal + tax_amount - withholding_amount

        try:
            # savepoint（ネストしたatomic）に包むのが重要。外側の @transaction.atomic を
            # そのまま使うと、IntegrityError発生時にPostgreSQLがトランザクション全体を
            # abort状態にしてしまい、以降のcatch節でのORM操作すら失敗する
            # （"current transaction is aborted" エラー）。savepointを切ることで、
            # 1社の競合失敗を残り全社の生成処理から隔離できる。
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    contractor=contractor,
                    invoice_no=_next_invoice_no(year_month, contractor.id),
                    issued_on=timezone.localdate(),
                    period_start=_period_start(year_month),
                    period_end=period_end,
                    tax_category=tax_category,
                    subtotal=subtotal,
                    tax_amount=tax_amount,
                    withholding_amount=withholding_amount,
                    payable_amount=payable,
                    exempt_deduction_percent=exempt_percent,
                    status=InvoiceStatus.DRAFT,
                    created_by=created_by,
                )
                InvoiceLine.objects.create(
                    invoice=invoice,
                    description=_line_description(rate.rate_type, record),
                    quantity=(record.hours or record.days or Decimal("1")) if record else Decimal("1"),
                    unit_price=rate.rate_amount,
                    amount=subtotal,
                    tax_category=tax_category,
                    withholding_applicable=contractor.withholding_target,
                )
        except IntegrityError:
            # uniq_active_invoice_per_contractor_period に弾かれた＝他のリクエストが
            # 一瞬早くこの外注先・対象月の請求書を作成済みだった（競合状態が実際に発生した
            # ケース）。エラーにせず「既に存在する」扱いにフォールバックし、
            # 呼び出し元には通常の重複スキップと同じ結果を返す。
            already_exists.append(contractor)
            continue
        created.append(invoice)

    return GenerationResult(created=created, skipped_no_record=skipped_no_record, already_exists=already_exists)


def _next_invoice_no(year_month: str, contractor_id: int) -> str:
    """対象月・外注先ごとの請求書番号。取消（赤伝）後の再発行では同一月・同一外注先に対して
    番号が衝突しうるため（設計書 第8.6章）、既存番号と衝突する場合は連番を付けて回避する。"""
    base = f"INV-{year_month}-{contractor_id:04d}"
    candidate = base
    suffix = 1
    while Invoice.objects.filter(invoice_no=candidate).exists():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _calc_subtotal(rate_type: str, rate_amount: Decimal, record: ContractorWorkRecord | None) -> Decimal | None:
    if record is None:
        return None
    from apps.contractors.models import RateType

    if rate_type == RateType.HOURLY:
        return calc_subtotal_hourly(record.hours, rate_amount) if record.hours else None
    if rate_type == RateType.DAILY:
        return calc_subtotal_daily(record.days, rate_amount) if record.days else None
    if rate_type == RateType.FIXED:
        return calc_subtotal_fixed(rate_amount) if record.fixed_applied else None
    return None


def _line_description(rate_type: str, record: ContractorWorkRecord | None) -> str:
    from apps.contractors.models import RateType

    if rate_type == RateType.HOURLY and record:
        return f"稼働 {record.hours}時間"
    if rate_type == RateType.DAILY and record:
        return f"稼働 {record.days}日"
    return "固定額"


def _period_start(year_month: str) -> date:
    year, month = (int(p) for p in year_month.split("-"))
    return date(year, month, 1)


def _last_day_of_period(year_month: str) -> date:
    import calendar

    year, month = (int(p) for p in year_month.split("-"))
    return date(year, month, calendar.monthrange(year, month)[1])
