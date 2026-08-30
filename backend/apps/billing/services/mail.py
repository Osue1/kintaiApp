"""請求書PDFの自動メール送信（設計書 第2.5章・第8.6章）。

本番は Amazon SES（バウンス検知つき）を想定するが、ローカル/開発では Django 標準の
コンソールバックエンドで代替する。差し替えは EMAIL_BACKEND の設定だけで完結する
（送信ログの形は InvoiceDelivery のまま変わらない）。
"""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage

from apps.billing.models import DeliveryStatus, Invoice, InvoiceDelivery
from apps.billing.services.pdf import read_pdf


def send_invoice_email(invoice: Invoice, recipient_email: str, pdf_key: str) -> InvoiceDelivery:
    subject = f"【{invoice.contractor.name} 様】{invoice.period_end:%Y年%m月}分 お支払い明細のご案内"
    body = (
        f"{invoice.contractor.name} 様\n\n"
        f"{invoice.period_start}〜{invoice.period_end} のお支払い明細を添付のとおりご案内いたします。\n"
        "内容にご確認事項がございましたら、発行日より7日以内にご連絡ください。"
        "期限までにご連絡がない場合は、内容をご確認いただいたものとして取り扱わせていただきます。\n\n"
        f"差引支払額: {invoice.payable_amount:,}円\n"
    )
    pdf_bytes = read_pdf(pdf_key)
    if pdf_bytes is None:
        raise FileNotFoundError(f"請求書PDFが見つかりません: {pdf_key}")

    email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient_email])
    # attach_file(ローカルパス限定)ではなく、ストレージから読んだバイト列をそのまま添付する
    # ことで、PDFの実体がどこに保存されているか（ローカルディスクかS3か）に email 側が
    # 関知しなくて済むようにしている。
    email.attach(f"{invoice.invoice_no}.pdf", pdf_bytes, "application/pdf")
    email.send()
    return InvoiceDelivery.objects.create(
        invoice=invoice, recipient_email=recipient_email, status=DeliveryStatus.SENT
    )
