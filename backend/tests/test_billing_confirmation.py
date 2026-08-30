"""仕入明細書の確認記録フロー（設計書 第8.5章）。"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import InvoiceConfirmation
from apps.billing.services.confirmation import (
    CONFIRM_PERIOD_DAYS,
    ConfirmationState,
    confirm_manually,
    deem_overdue_confirmations,
    notify_for_confirmation,
    should_deem_confirmed,
)
from apps.contractors.models import Contractor, ContractorRate, ContractorWorkRecord

pytestmark = pytest.mark.django_db


# --- 純関数: should_deem_confirmed ---

def test_should_deem_confirmed_false_when_never_notified():
    state = ConfirmationState(notified_at=None, confirm_deadline=date(2026, 1, 1), confirmed_at=None)
    assert should_deem_confirmed(state, as_of=date(2026, 6, 1)) is False


def test_should_deem_confirmed_false_when_already_confirmed():
    state = ConfirmationState(
        notified_at=timezone.now(), confirm_deadline=date(2026, 1, 1), confirmed_at=timezone.now()
    )
    assert should_deem_confirmed(state, as_of=date(2026, 6, 1)) is False


def test_should_deem_confirmed_boundary_exactly_on_deadline_is_not_yet_overdue():
    """締切当日はまだ猶予内（超過扱いにしない）— 境界値。"""
    state = ConfirmationState(notified_at=timezone.now(), confirm_deadline=date(2026, 1, 15), confirmed_at=None)
    assert should_deem_confirmed(state, as_of=date(2026, 1, 15)) is False


def test_should_deem_confirmed_true_the_day_after_deadline():
    state = ConfirmationState(notified_at=timezone.now(), confirm_deadline=date(2026, 1, 15), confirmed_at=None)
    assert should_deem_confirmed(state, as_of=date(2026, 1, 16)) is True


# --- DB統合: notify_for_confirmation / confirm_manually / deem_overdue_confirmations ---

@pytest.fixture
def contractor(db):
    c = Contractor.objects.create(
        name="テスト外注先", email="vendor@example.com", tax_category="taxable", withholding_target=True,
        closing_day=31, payment_month_offset=1, payment_day=10,
    )
    ContractorRate.objects.create(contractor=c, rate_type="hourly", rate_amount=Decimal("4500"), effective_from=date(2024, 1, 1))
    return c


@pytest.fixture
def invoice(contractor, admin_user):
    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-07", hours=Decimal("40"))
    from apps.billing.services.generate import generate_invoices_for_month

    result = generate_invoices_for_month("2026-07", created_by=admin_user)
    return result.created[0]


def test_notify_for_confirmation_sets_deadline_n_days_ahead(invoice):
    confirmation = notify_for_confirmation(invoice)
    assert confirmation.notified_at is not None
    assert confirmation.confirm_deadline == timezone.localdate() + timedelta(days=CONFIRM_PERIOD_DAYS)
    assert confirmation.confirmed_at is None


def test_confirm_manually_marks_confirmed_with_manual_method(invoice):
    confirmation = notify_for_confirmation(invoice)
    confirm_manually(confirmation)
    confirmation.refresh_from_db()
    assert confirmation.confirmed_at is not None
    assert confirmation.confirm_method == "manual"


def test_deem_overdue_confirmations_only_affects_overdue_unconfirmed(invoice, contractor, admin_user):
    from apps.billing.services.generate import generate_invoices_for_month

    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-06", hours=Decimal("10"))
    other_invoice = generate_invoices_for_month("2026-06", created_by=admin_user).created[0]

    overdue = notify_for_confirmation(invoice)
    overdue.confirm_deadline = timezone.localdate() - timedelta(days=1)
    overdue.save(update_fields=["confirm_deadline"])

    not_yet_due = notify_for_confirmation(other_invoice)  # 期限内なので対象外

    updated = deem_overdue_confirmations()

    assert [c.id for c in updated] == [overdue.id]
    overdue.refresh_from_db()
    assert overdue.confirmed_at is not None
    assert overdue.confirm_method == "deemed_after_deadline"

    not_yet_due.refresh_from_db()
    assert not_yet_due.confirmed_at is None


def test_confirm_invoices_command_runs_end_to_end(invoice):
    confirmation = notify_for_confirmation(invoice)
    confirmation.confirm_deadline = timezone.localdate() - timedelta(days=1)
    confirmation.save(update_fields=["confirm_deadline"])

    call_command("confirm_invoices")

    confirmation.refresh_from_db()
    assert confirmation.confirmed_at is not None


# --- API ---

def test_send_invoice_creates_confirmation_record(client, admin_user, invoice):
    client.force_login(admin_user)
    res = client.post(reverse("invoices-send", args=[invoice.id]))
    assert res.status_code == 200
    assert res.json()["confirm_deadline"] is not None
    assert InvoiceConfirmation.objects.filter(invoice=invoice).exists()


def test_confirm_endpoint_rejects_when_not_yet_sent(client, admin_user, invoice):
    client.force_login(admin_user)
    res = client.post(reverse("invoices-confirm", args=[invoice.id]))
    assert res.status_code == 400
    assert res.json()["code"] == "not_notified"


def test_confirm_endpoint_marks_confirmed_after_send(client, admin_user, invoice):
    client.force_login(admin_user)
    client.post(reverse("invoices-send", args=[invoice.id]))

    res = client.post(reverse("invoices-confirm", args=[invoice.id]))
    assert res.status_code == 200
    assert res.json()["confirmed_at"] is not None
    assert res.json()["confirm_method"] == "manual"


def test_confirm_endpoint_rejects_double_confirmation(client, admin_user, invoice):
    client.force_login(admin_user)
    client.post(reverse("invoices-send", args=[invoice.id]))
    client.post(reverse("invoices-confirm", args=[invoice.id]))

    res = client.post(reverse("invoices-confirm", args=[invoice.id]))
    assert res.status_code == 400
    assert res.json()["code"] == "already_confirmed"


def test_confirm_endpoint_writes_audit_log(client, admin_user, invoice):
    from apps.accounts.models import AuditLog

    client.force_login(admin_user)
    client.post(reverse("invoices-send", args=[invoice.id]))
    client.post(reverse("invoices-confirm", args=[invoice.id]))

    assert AuditLog.objects.filter(action="invoice_confirm", target_type="Invoice", target_id=invoice.id).exists()
