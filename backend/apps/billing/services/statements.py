"""支払調書の年間一括生成（設計書 第8.7章）。

暦年（1/1〜12/31）の支払確定（発行済み・送信済み）ベースで集計し、同一支払先への
年間支払金額が5万円超のものだけを対象とする。
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.billing.models import Invoice, InvoiceStatus, WithholdingStatement
from apps.contractors.models import Contractor

REPORTING_THRESHOLD = Decimal("50000")


@transaction.atomic
def generate_annual_statements(year: int) -> list[WithholdingStatement]:
    created: list[WithholdingStatement] = []
    contractors = Contractor.objects.filter(
        invoices__issued_on__year=year, invoices__status__in=[InvoiceStatus.ISSUED, InvoiceStatus.SENT]
    ).distinct()

    for contractor in contractors:
        agg = Invoice.objects.filter(
            contractor=contractor,
            issued_on__year=year,
            status__in=[InvoiceStatus.ISSUED, InvoiceStatus.SENT],
        ).aggregate(total_payment=Sum("subtotal"), total_withholding=Sum("withholding_amount"))
        total_payment = agg["total_payment"] or Decimal("0")
        total_withholding = agg["total_withholding"] or Decimal("0")
        if total_payment <= REPORTING_THRESHOLD:
            continue

        statement, _ = WithholdingStatement.objects.update_or_create(
            contractor=contractor,
            year=year,
            defaults={"total_payment": total_payment, "total_withholding": total_withholding},
        )
        created.append(statement)

    return created
