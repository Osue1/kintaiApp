"""請求書PDFのストレージ抽象化（設計上の欠陥の修正確認）。

以前は apps/billing/services/pdf.py が pathlib.Path で直接ローカルファイルシステムへ
書き込んでおり、config/settings/base.py の STORAGES 設定（本番はCloud Storageへ差し替える
想定）が実質機能していなかった。django.core.files.storage.default_storage 経由に
統一したことを確認する。
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.files.storage import default_storage
from django.urls import reverse

from apps.billing.services.generate import generate_invoices_for_month
from apps.billing.services.mail import send_invoice_email
from apps.billing.services.pdf import read_pdf, render_invoice_pdf
from apps.contractors.models import Contractor, ContractorRate, ContractorWorkRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def contractor(db):
    c = Contractor.objects.create(
        name="PDF保存検証用外注先", email="vendor@example.com", tax_category="taxable",
        withholding_target=True, closing_day=31, payment_month_offset=1, payment_day=10,
    )
    ContractorRate.objects.create(contractor=c, rate_type="hourly", rate_amount=Decimal("4500"), effective_from=date(2024, 1, 1))
    return c


@pytest.fixture
def invoice(contractor, admin_user):
    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-07", hours=Decimal("40"))
    return generate_invoices_for_month("2026-07", created_by=admin_user).created[0]


def test_render_invoice_pdf_saves_via_default_storage_and_sets_pdf_key(invoice):
    key = render_invoice_pdf(invoice)

    assert key == invoice.pdf_key
    assert key.startswith("invoices/")
    assert default_storage.exists(key)


def test_read_pdf_returns_bytes_for_existing_key_and_none_for_missing(invoice):
    key = render_invoice_pdf(invoice)

    content = read_pdf(key)
    assert content is not None
    assert content[:4] == b"%PDF"

    assert read_pdf("invoices/does-not-exist.pdf") is None
    assert read_pdf("") is None


def test_regenerating_pdf_overwrites_rather_than_accumulating_storage_entries(invoice):
    """境界値: Django標準ストレージのsave()は同名キーが既にあると別名
    （例: INV-xxx_AbCdEf.pdf）を自動生成し上書きしない仕様のため、事前削除の対策を
    入れていないと再生成のたびにストレージ上のファイルが増え続けてしまう。
    invoice.pdf_key（呼び出し側が事前に決め打ちした文字列）が変わらないことだけを見ても、
    実際に別名保存されバレない可能性があるため、ストレージのディレクトリ実体を直接調べる。
    """
    key1 = render_invoice_pdf(invoice)
    render_invoice_pdf(invoice)

    directory, _ = key1.rsplit("/", 1)
    _, filenames = default_storage.listdir(directory)
    matching = [name for name in filenames if name.startswith(invoice.invoice_no)]
    assert matching == [f"{invoice.invoice_no}.pdf"], (
        f"再生成のたびにストレージ上のファイルが増えている（別名保存されている）: {matching}"
    )


def test_invoice_pdf_download_endpoint_serves_from_storage(client, admin_user, invoice):
    client.force_login(admin_user)
    res = client.get(reverse("invoices-pdf", args=[invoice.id]))
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"
    assert f"{invoice.invoice_no}.pdf" in res["Content-Disposition"]


def test_invoice_pdf_download_regenerates_when_storage_entry_is_missing(client, admin_user, invoice):
    """pdf_key はセットされているがストレージ実体が失われているケース
    （例: ローカルディスクの掃除、ストレージ側の障害）でも、その場で再生成して返せること。"""
    key = render_invoice_pdf(invoice)
    default_storage.delete(key)
    assert not default_storage.exists(key)

    client.force_login(admin_user)
    res = client.get(reverse("invoices-pdf", args=[invoice.id]))
    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"


def test_send_invoice_email_attaches_pdf_read_from_storage(invoice, contractor):
    from django.core import mail

    key = render_invoice_pdf(invoice)
    send_invoice_email(invoice, contractor.email, key)

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert len(sent.attachments) == 1
    filename, content, mimetype = sent.attachments[0]
    assert filename == f"{invoice.invoice_no}.pdf"
    assert content[:4] == b"%PDF"
    assert mimetype == "application/pdf"


def test_send_invoice_email_raises_clear_error_when_pdf_key_missing(invoice, contractor):
    with pytest.raises(FileNotFoundError):
        send_invoice_email(invoice, contractor.email, "invoices/does-not-exist.pdf")
