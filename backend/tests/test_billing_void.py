"""請求書の取消（赤伝）・再発行フロー（設計書 第8.6章）。"""
import threading
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Role
from apps.billing.models import Invoice, InvoiceStatus
from apps.billing.services.void import InvoiceVoidError, void_invoice
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


@pytest.fixture
def issued_invoice(contractor, admin_user):
    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-07", hours=Decimal("40"))
    from apps.billing.services.generate import generate_invoices_for_month

    result = generate_invoices_for_month("2026-07", created_by=admin_user)
    invoice = result.created[0]
    invoice.status = InvoiceStatus.ISSUED
    invoice.save(update_fields=["status"])
    return invoice


def test_void_invoice_creates_negated_reversal_and_marks_original_void(issued_invoice, admin_user):
    reversal = void_invoice(issued_invoice, actor=admin_user)

    issued_invoice.refresh_from_db()
    assert issued_invoice.status == InvoiceStatus.VOID

    assert reversal.status == InvoiceStatus.VOID
    assert reversal.void_of_id == issued_invoice.id
    assert reversal.subtotal == -issued_invoice.subtotal
    assert reversal.tax_amount == -issued_invoice.tax_amount
    assert reversal.withholding_amount == -issued_invoice.withholding_amount
    assert reversal.payable_amount == -issued_invoice.payable_amount
    assert reversal.invoice_no == f"{issued_invoice.invoice_no}-R"

    original_lines = list(issued_invoice.lines.all())
    reversal_lines = list(reversal.lines.all())
    assert len(reversal_lines) == len(original_lines)
    for orig, rev in zip(original_lines, reversal_lines, strict=True):
        assert rev.amount == -orig.amount
        assert rev.description == f"（取消）{orig.description}"


def test_void_invoice_rejects_draft(contractor):
    draft = Invoice.objects.create(
        contractor=contractor, invoice_no="DRAFT-1", issued_on="2026-07-31",
        period_start="2026-07-01", period_end="2026-07-31", tax_category="taxable",
        subtotal=1000, tax_amount=100, withholding_amount=0, payable_amount=1100,
        status=InvoiceStatus.DRAFT,
    )
    with pytest.raises(InvoiceVoidError):
        void_invoice(draft, actor=None)


def test_void_invoice_rejects_already_void(issued_invoice, admin_user):
    void_invoice(issued_invoice, actor=admin_user)
    issued_invoice.refresh_from_db()
    with pytest.raises(InvoiceVoidError):
        void_invoice(issued_invoice, actor=admin_user)


def test_void_invoice_no_collision_when_reversing_twice_under_same_base(contractor, admin_user):
    """同じ番号ベースの請求書が既にある場合でも赤伝番号が衝突しないこと（境界値）。"""
    inv1 = Invoice.objects.create(
        contractor=contractor, invoice_no="INV-1", issued_on="2026-07-31",
        period_start="2026-07-01", period_end="2026-07-31", tax_category="taxable",
        subtotal=1000, tax_amount=100, withholding_amount=0, payable_amount=1100,
        status=InvoiceStatus.ISSUED,
    )
    # あらかじめ "INV-1-R" が存在する状態を作っておく
    Invoice.objects.create(
        contractor=contractor, invoice_no="INV-1-R", issued_on="2026-07-31",
        period_start="2026-07-01", period_end="2026-07-31", tax_category="taxable",
        subtotal=0, tax_amount=0, withholding_amount=0, payable_amount=0,
        status=InvoiceStatus.VOID,
    )
    reversal = void_invoice(inv1, actor=admin_user)
    assert reversal.invoice_no == "INV-1-R2"


def test_reissue_after_void_generates_fresh_invoice_for_same_period(client, admin_user, issued_invoice, contractor):
    """取消後、同じ月・外注先に対して一括生成を再実行すると新しい請求書が生成される（再発行）。"""
    client.force_login(admin_user)
    res = client.post(reverse("invoices-void", args=[issued_invoice.id]))
    assert res.status_code == 201

    res = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json")
    assert res.status_code == 200
    assert res.json()["created_count"] == 1

    new_invoice_id = res.json()["created"][0]["id"]
    assert new_invoice_id not in (issued_invoice.id,)
    new_invoice = Invoice.objects.get(id=new_invoice_id)
    assert new_invoice.status == InvoiceStatus.DRAFT


def test_void_endpoint_writes_audit_log(client, admin_user, issued_invoice):
    from apps.accounts.models import AuditLog

    client.force_login(admin_user)
    res = client.post(reverse("invoices-void", args=[issued_invoice.id]))
    assert res.status_code == 201

    log = AuditLog.objects.get(action="invoice_void", target_type="Invoice", target_id=issued_invoice.id)
    assert log.actor == admin_user
    assert log.after["reversal_invoice_no"] == f"{issued_invoice.invoice_no}-R"


def test_void_endpoint_rejects_already_void_invoice(client, admin_user, issued_invoice):
    client.force_login(admin_user)
    client.post(reverse("invoices-void", args=[issued_invoice.id]))
    res = client.post(reverse("invoices-void", args=[issued_invoice.id]))
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_state"


def test_next_invoice_no_avoids_collision_after_void_and_reissue(client, admin_user, issued_invoice):
    """取消→再発行を2回繰り返しても請求書番号が衝突しないこと（第8.6章、境界値）。"""
    from apps.billing.services.generate import _next_invoice_no

    original_no = issued_invoice.invoice_no

    client.force_login(admin_user)
    res = client.post(reverse("invoices-void", args=[issued_invoice.id]))
    assert res.status_code == 201

    res = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json")
    assert res.json()["created_count"] == 1
    reissued_no = res.json()["created"][0]["invoice_no"]
    assert reissued_no != original_no

    # 2回目の取消・再発行でも番号が衝突しないこと
    reissued = Invoice.objects.get(invoice_no=reissued_no)
    reissued.status = InvoiceStatus.ISSUED
    reissued.save(update_fields=["status"])
    res = client.post(reverse("invoices-void", args=[reissued.id]))
    assert res.status_code == 201

    res = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json")
    assert res.json()["created_count"] == 1
    second_reissued_no = res.json()["created"][0]["invoice_no"]
    assert len({original_no, reissued_no, second_reissued_no}) == 3

    # ヘルパー単体でも、既存の番号群を全て避けること
    assert _next_invoice_no("2026-07", issued_invoice.contractor_id) not in {original_no, reissued_no, second_reissued_no}


@pytest.mark.django_db(transaction=True)
def test_concurrent_void_requests_produce_exactly_one_reversal():
    """同一請求書への取消操作が同時に2回走っても、赤伝は1枚しか発行されないこと（境界値: 競合状態）。

    通常のテストはトランザクションをロールバックして分離するため、別スレッドから見えるDB状態を
    シミュレートできない。ここでは transaction=True（実DBへの本コミット）＋threading で
    2つの取消リクエストを本当に同時実行し、select_for_update() による直列化が機能して
    いることを検証する。db フィクスチャ（ロールバック方式）と transactional_db は
    併用できないため、必要なデータはこのテスト内で直接作成する。
    """
    contractor = Contractor.objects.create(
        name="並行実行検証用外注先", tax_category="taxable", withholding_target=True,
        closing_day=31, payment_month_offset=1, payment_day=10,
    )
    ContractorRate.objects.create(
        contractor=contractor, rate_type="hourly", rate_amount=Decimal("4500"), effective_from=date(2024, 1, 1)
    )
    admin = get_user_model().objects.create_user(
        email="race-admin@example.com", password="correct-horse-battery", name="競合検証管理者", role=Role.ADMIN,
    )
    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-07", hours=Decimal("40"))

    from apps.billing.services.generate import generate_invoices_for_month

    invoice = generate_invoices_for_month("2026-07", created_by=admin).created[0]
    invoice.status = InvoiceStatus.ISSUED
    invoice.save(update_fields=["status"])

    outcomes: list[str] = []
    start_barrier = threading.Barrier(2)

    def attempt_void() -> None:
        from django.db import connection

        try:
            # 2スレッドがほぼ同時にDBへ到達するよう足並みを揃える
            start_barrier.wait(timeout=5)
            void_invoice(invoice, actor=admin)
            outcomes.append("succeeded")
        except InvoiceVoidError:
            outcomes.append("rejected")
        finally:
            # スレッドごとに独立したDB接続が張られるため、明示的に閉じてリークを防ぐ
            connection.close()

    threads = [threading.Thread(target=attempt_void) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(outcomes) == ["rejected", "succeeded"]
    assert Invoice.objects.filter(void_of=invoice).count() == 1
