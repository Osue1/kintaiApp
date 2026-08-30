"""支払調書の年間一括出力・PDFダウンロード（設計上の欠陥の修正確認: render_withholding_
statement_pdf() は存在していたが、それを呼ぶAPI・ダウンロード導線が一つも無かった）。"""
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.billing.models import Invoice, InvoiceStatus, WithholdingStatement
from apps.contractors.models import Contractor

pytestmark = pytest.mark.django_db


@pytest.fixture
def contractor(db):
    return Contractor.objects.create(
        name="支払調書検証用外注先", email="vendor@example.com", tax_category="taxable",
        withholding_target=True, closing_day=31, payment_month_offset=1, payment_day=10,
    )


def _issued_invoice(contractor, subtotal: Decimal, withholding: Decimal, issued_on: date) -> Invoice:
    return Invoice.objects.create(
        contractor=contractor,
        invoice_no=f"STMT-{contractor.id}-{issued_on.isoformat()}",
        issued_on=issued_on,
        period_start=issued_on.replace(day=1),
        period_end=issued_on,
        tax_category="taxable",
        subtotal=subtotal,
        tax_amount=subtotal * Decimal("0.1"),
        withholding_amount=withholding,
        payable_amount=subtotal - withholding,
        status=InvoiceStatus.ISSUED,
    )


def test_issuing_annual_statements_creates_records_for_contractors_above_threshold(client, admin_user, contractor):
    _issued_invoice(contractor, Decimal("100000"), Decimal("10210"), date(2026, 6, 30))

    client.force_login(admin_user)
    res = client.post(reverse("withholding-statements"), {"year": 2026}, content_type="application/json")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["contractor_name"] == contractor.name
    assert Decimal(str(body[0]["total_payment"])) == Decimal("100000")


def test_issuing_annual_statements_skips_contractors_below_reporting_threshold(client, admin_user, contractor):
    """境界値: 年間支払額が5万円ちょうどは対象外（設計書 第8.7章、5万円"超"のみ対象）。"""
    _issued_invoice(contractor, Decimal("50000"), Decimal("0"), date(2026, 6, 30))

    client.force_login(admin_user)
    res = client.post(reverse("withholding-statements"), {"year": 2026}, content_type="application/json")
    assert res.json() == []
    assert not WithholdingStatement.objects.exists()


def test_list_statements_can_filter_by_year(client, admin_user, contractor):
    _issued_invoice(contractor, Decimal("100000"), Decimal("10210"), date(2025, 6, 30))
    _issued_invoice(contractor, Decimal("200000"), Decimal("20420"), date(2026, 6, 30))
    client.force_login(admin_user)
    client.post(reverse("withholding-statements"), {"year": 2025}, content_type="application/json")
    client.post(reverse("withholding-statements"), {"year": 2026}, content_type="application/json")

    res = client.get(reverse("withholding-statements"), {"year": 2026})
    body = res.json()
    assert len(body) == 1
    assert body[0]["year"] == 2026


def test_download_statement_pdf_generates_on_first_request(client, admin_user, contractor):
    _issued_invoice(contractor, Decimal("100000"), Decimal("10210"), date(2026, 6, 30))
    client.force_login(admin_user)
    client.post(reverse("withholding-statements"), {"year": 2026}, content_type="application/json")
    statement = WithholdingStatement.objects.get(contractor=contractor, year=2026)
    assert statement.pdf_key == ""  # 出力時点ではまだPDFは作られない（ダウンロード時に遅延生成）

    res = client.get(reverse("withholding-statements-pdf", args=[statement.id]))
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"
    assert f"withholding_statement_{contractor.id}_2026.pdf" in res["Content-Disposition"]

    statement.refresh_from_db()
    assert statement.pdf_key != ""


def test_download_statement_pdf_regenerates_when_storage_entry_missing(client, admin_user, contractor):
    from django.core.files.storage import default_storage

    _issued_invoice(contractor, Decimal("100000"), Decimal("10210"), date(2026, 6, 30))
    client.force_login(admin_user)
    client.post(reverse("withholding-statements"), {"year": 2026}, content_type="application/json")
    statement = WithholdingStatement.objects.get(contractor=contractor, year=2026)

    client.get(reverse("withholding-statements-pdf", args=[statement.id]))
    statement.refresh_from_db()
    default_storage.delete(statement.pdf_key)

    res = client.get(reverse("withholding-statements-pdf", args=[statement.id]))
    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"


def test_download_statement_pdf_404_for_unknown_id(client, admin_user):
    client.force_login(admin_user)
    res = client.get(reverse("withholding-statements-pdf", args=[999999]))
    assert res.status_code == 404


def test_non_admin_cannot_download_statement_pdf(client, employee, admin_user, contractor):
    _issued_invoice(contractor, Decimal("100000"), Decimal("10210"), date(2026, 6, 30))
    client.force_login(admin_user)
    client.post(reverse("withholding-statements"), {"year": 2026}, content_type="application/json")
    statement = WithholdingStatement.objects.get(contractor=contractor, year=2026)

    client.force_login(employee)
    res = client.get(reverse("withholding-statements-pdf", args=[statement.id]))
    assert res.status_code == 403
