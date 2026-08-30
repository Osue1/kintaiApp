"""請求書・支払調書PDFの生成（設計書 第2.4章 WeasyPrint + 第8.4章 インボイス記載事項）。

本番は Cloud Storage に署名付きURLで配布する設計（設計書 第3章・第12.1章）で、
config/settings/base.py の STORAGES["default"] がその差し替え口として用意されている
（本番では S3 等のバックエンドに設定を変えるだけで良いはずだった）。ところが以前は
ここで pathlib.Path を使って直接ローカルファイルシステムへ書き込んでおり、STORAGES の
設定を差し替えても実際には何も変わらないという設計と実装の不整合があった
（アプリを複数インスタンス構成にすると、PDFを生成したインスタンス以外では
ダウンロードできなくなる／再デプロイで消える）。

django.core.files.storage.default_storage 経由に統一したことで、本番で
STORAGES["default"]["BACKEND"] を S3 向けバックエンド（例: django-storages の
storages.backends.s3.S3Storage）に差し替えるだけで複数インスタンス構成でも
PDFを正しく共有できるようになる（EMAIL_BACKEND の差し替えと同じ考え方。
apps/billing/services/mail.py 参照）。
"""
from __future__ import annotations

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
from weasyprint import HTML

from apps.billing.models import Invoice, WithholdingStatement

INVOICE_STORAGE_PREFIX = "invoices"
STATEMENT_STORAGE_PREFIX = "withholding_statements"


def render_invoice_pdf(invoice: Invoice) -> str:
    """PDFを生成してストレージへ保存し、保存先キー（invoice.pdf_key と同じ値）を返す。"""
    from apps.accounts.models import Company

    company = Company.get_solo()
    html = render_to_string(
        "billing/invoice.html",
        {
            "invoice": invoice,
            "company": company,
            "contractor": invoice.contractor,
            "lines": invoice.lines.all(),
        },
    )
    pdf_bytes = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
    key = f"{INVOICE_STORAGE_PREFIX}/{invoice.invoice_no}.pdf"
    _save(key, pdf_bytes)
    invoice.pdf_key = key
    invoice.save(update_fields=["pdf_key"])
    return key


def render_withholding_statement_pdf(statement: WithholdingStatement) -> str:
    from apps.accounts.models import Company

    company = Company.get_solo()
    html = render_to_string(
        "billing/withholding_statement.html",
        {"statement": statement, "company": company, "contractor": statement.contractor},
    )
    pdf_bytes = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
    key = f"{STATEMENT_STORAGE_PREFIX}/{statement.contractor_id}-{statement.year}.pdf"
    _save(key, pdf_bytes)
    statement.pdf_key = key
    statement.save(update_fields=["pdf_key"])
    return key


def read_pdf(key: str) -> bytes | None:
    """ストレージから指定キーのPDFを読み出す。存在しなければ None。"""
    if not key or not default_storage.exists(key):
        return None
    with default_storage.open(key, "rb") as f:
        return f.read()


def _save(key: str, content: bytes) -> None:
    # Django標準ストレージの save() は同名キーが既にあると別名（例: xxx_AbCdEf.pdf）を
    # 自動生成してしまう（上書きしない）仕様のため、再生成時に無限にキーが増えないよう
    # 先に既存分を消してから保存する。
    if default_storage.exists(key):
        default_storage.delete(key)
    default_storage.save(key, ContentFile(content))
