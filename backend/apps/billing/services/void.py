"""請求書の取消（赤伝）・再発行フロー（設計書 第8.6章）。

発行確定・送信済みの請求書に誤りが見つかった場合、内容を直接書き換えるのではなく、
金額を反転した赤伝（取消請求書）を発行して原請求書を取消状態にする。
再発行そのものは既存の generate_invoices_for_month が「対象月・外注先で有効な（=VOID
以外の）請求書が既に存在するか」で生成要否を判定しているため、原請求書を VOID にするだけで
通常の一括生成フローに乗り、正しい内容の請求書を再発行できる（services/generate.py 参照）。
"""
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceLine, InvoiceStatus


class InvoiceVoidError(Exception):
    """取消できない状態の請求書に対する操作。"""


@transaction.atomic
def void_invoice(invoice: Invoice, actor) -> Invoice:
    """`invoice` を取消し、金額を反転した赤伝請求書を新規作成して返す。

    同一請求書に対して取消操作が同時に2回走る競合状態に注意する必要がある
    （例: 二重クリック、ネットワーク再送、別々の管理者による同時操作）。呼び出し元
    （view）から渡ってくる `invoice` は取消判定より前の時点で読み込まれたインスタンス
    であり、その後の状態変化を反映していない可能性がある。ここで改めて
    select_for_update() により当該行をロックして再取得し、ロック後の最新状態に対して
    ステータス判定を行うことで、先着した一方だけが処理を完了し、後着はロック解放後に
    「既に取消済み」を正しく検知して弾かれるようにする。
    請求書一括生成（services/generate.py）の競合と違い、赤伝の請求書番号は
    _reversal_invoice_no() が採番のたびに衝突を避けてしまうため、DBの一意制約だけでは
    同時実行時の二重発行（赤伝が2枚できてしまう）を検知できない。select_for_update()
    による直列化が必須の防御線となる。
    """
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)

    if invoice.status == InvoiceStatus.DRAFT:
        raise InvoiceVoidError("下書きの請求書は取消の対象外です。内容を直接修正してください。")
    if invoice.status == InvoiceStatus.VOID:
        raise InvoiceVoidError("この請求書は既に取消済みです。")

    reversal = Invoice.objects.create(
        contractor=invoice.contractor,
        invoice_no=_reversal_invoice_no(invoice),
        issued_on=timezone.localdate(),
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        tax_category=invoice.tax_category,
        subtotal=-invoice.subtotal,
        tax_amount=-invoice.tax_amount,
        withholding_amount=-invoice.withholding_amount,
        payable_amount=-invoice.payable_amount,
        exempt_deduction_percent=invoice.exempt_deduction_percent,
        status=InvoiceStatus.VOID,
        void_of=invoice,
        created_by=actor,
    )
    for line in invoice.lines.all():
        InvoiceLine.objects.create(
            invoice=reversal,
            description=f"（取消）{line.description}",
            quantity=line.quantity,
            unit_price=line.unit_price,
            amount=-line.amount,
            tax_category=line.tax_category,
            withholding_applicable=line.withholding_applicable,
        )

    invoice.status = InvoiceStatus.VOID
    invoice.save(update_fields=["status"])
    return reversal


def _reversal_invoice_no(invoice: Invoice) -> str:
    base = f"{invoice.invoice_no}-R"
    candidate = base
    suffix = 1
    while Invoice.objects.filter(invoice_no=candidate).exists():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate
