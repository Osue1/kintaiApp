"""請求書生成APIの統合テスト（税マスタはデータマイグレーションで投入済みのものを使う）。"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.billing.models import Invoice, InvoiceStatus
from apps.billing.services.generate import generate_invoices_for_month
from apps.contractors.models import Contractor, ContractorRate, ContractorWorkRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def contractor(db):
    c = Contractor.objects.create(
        name="テスト外注先",
        email="vendor@example.com",
        tax_category="taxable",
        withholding_target=True,
        closing_day=31,
        payment_month_offset=1,
        payment_day=10,
    )
    ContractorRate.objects.create(
        contractor=c, rate_type="hourly", rate_amount=Decimal("4500"), effective_from=date(2024, 1, 1)
    )
    return c


def test_generate_invoice_computes_tax_and_withholding(client, admin_user, contractor):
    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-07", hours=Decimal("40"))

    client.force_login(admin_user)
    res = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json")
    assert res.status_code == 200
    body = res.json()
    assert body["created_count"] == 1

    invoice = body["created"][0]
    # 40h * 4500 = 180,000円
    assert Decimal(str(invoice["subtotal"])) == Decimal("180000")
    assert Decimal(str(invoice["tax_amount"])) == Decimal("18000")
    # 源泉徴収 180,000 * 10.21% = 18,378円
    assert Decimal(str(invoice["withholding_amount"])) == Decimal("18378")
    assert Decimal(str(invoice["payable_amount"])) == Decimal("179622")


def test_generate_invoice_skips_contractor_without_work_record(client, admin_user, contractor):
    client.force_login(admin_user)
    res = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json")
    assert res.json()["created_count"] == 0
    assert res.json()["skipped_no_record_count"] == 1


def test_generate_invoice_is_idempotent_per_month(client, admin_user, contractor):
    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-07", hours=Decimal("40"))
    client.force_login(admin_user)
    client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json")
    res = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json")
    assert res.json()["created_count"] == 0
    assert res.json()["already_exists_count"] == 1


def test_non_admin_cannot_generate_invoices(client, employee):
    client.force_login(employee)
    res = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json")
    assert res.status_code == 403


def _invoice_kwargs(contractor, period_end: date, status: str) -> dict:
    return dict(
        contractor=contractor,
        invoice_no=f"RACE-{status}-{period_end.isoformat()}",
        issued_on=period_end,
        period_start=period_end.replace(day=1),
        period_end=period_end,
        tax_category="taxable",
        subtotal=Decimal("1000"),
        tax_amount=Decimal("100"),
        withholding_amount=Decimal("0"),
        payable_amount=Decimal("1100"),
        status=status,
    )


def test_db_constraint_rejects_second_active_invoice_for_same_contractor_period(contractor):
    """uniq_active_invoice_per_contractor_period の直接検証。
    同一外注先・同一対象月のDRAFT/ISSUED/SENT請求書は2件同時に存在できないこと（境界値: 競合状態の最終防衛線）。"""
    period_end = date(2026, 7, 31)
    Invoice.objects.create(**_invoice_kwargs(contractor, period_end, InvoiceStatus.DRAFT))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Invoice.objects.create(**_invoice_kwargs(contractor, period_end, InvoiceStatus.ISSUED))


def test_db_constraint_allows_void_invoice_alongside_active_one(contractor):
    """取消済み(VOID)の請求書は一意制約の対象外 — 赤伝発行後の再発行フローを妨げないこと。"""
    period_end = date(2026, 7, 31)
    Invoice.objects.create(**_invoice_kwargs(contractor, period_end, InvoiceStatus.VOID))
    # 例外を送出しないことを確認する（VOIDは制約の対象外なので共存できる）
    Invoice.objects.create(**_invoice_kwargs(contractor, period_end, InvoiceStatus.DRAFT))


def test_generate_invoice_falls_back_to_already_exists_when_race_loses_to_db_constraint(
    client, admin_user, contractor
):
    """一括生成中の存在チェックをすり抜けて競合が実際に起きた場合（2重リクエスト等）でも、
    500エラーにならずスキップ扱いに正しくフォールバックすること。
    実際の競合状態は同期的なテストでは再現しづらいため、存在チェック(exists)が「見逃す」
    状況をモックで作り、DB制約が最終防衛線として機能することを検証する。"""
    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-07", hours=Decimal("40"))
    period_end = date(2026, 7, 31)
    # 「他のリクエストが一瞬早く作成済み」の状態を先に作っておく
    Invoice.objects.create(**_invoice_kwargs(contractor, period_end, InvoiceStatus.DRAFT))

    # exists() だけを常にFalseにすり替え、事前チェックが競合を見逃したケースを模擬する
    # （このテストの対象コードでは exists() 呼び出しが1箇所しかないため、グローバルな
    # パッチでも副作用の心配はない）
    with patch("django.db.models.QuerySet.exists", return_value=False):
        result = generate_invoices_for_month("2026-07", created_by=admin_user)

    assert result.created == []
    assert [c.id for c in result.already_exists] == [contractor.id]
    # 競合で弾かれた分を除き、DB上は最初に作った1件だけが残っていること（二重発行していない）
    assert Invoice.objects.filter(contractor=contractor, period_end=period_end).count() == 1
