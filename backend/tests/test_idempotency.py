"""`Idempotency-Key` ヘッダによる打刻・請求書生成の二重実行防止。"""
from datetime import date
from decimal import Decimal

import pytest
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.response import Response

from apps.common.idempotency import with_idempotency
from apps.common.models import IdempotencyKey
from apps.contractors.models import Contractor, ContractorRate, ContractorWorkRecord

pytestmark = pytest.mark.django_db


# --- with_idempotency ヘルパー単体 ---

def _request(key: str | None, user=None):
    req = RequestFactory().post("/api/v1/whatever")
    if key is not None:
        req.META["HTTP_IDEMPOTENCY_KEY"] = key
    req.user = user
    return req


def test_without_key_header_handler_runs_every_time(admin_user):
    calls = 0

    def handler():
        nonlocal calls
        calls += 1
        return Response({"n": calls}, status=200)

    req = _request(None, admin_user)
    with_idempotency(req, "test-ep", handler)
    with_idempotency(req, "test-ep", handler)
    assert calls == 2


def test_with_key_header_handler_runs_only_once(admin_user):
    calls = 0

    def handler():
        nonlocal calls
        calls += 1
        return Response({"n": calls}, status=201)

    req1 = _request("abc-123", admin_user)
    res1 = with_idempotency(req1, "test-ep", handler)
    req2 = _request("abc-123", admin_user)
    res2 = with_idempotency(req2, "test-ep", handler)

    assert calls == 1
    assert res1.data == {"n": 1}
    assert res2.data == {"n": 1}
    assert res2.status_code == 201


def test_same_key_different_endpoint_does_not_collide(admin_user):
    calls = 0

    def handler():
        nonlocal calls
        calls += 1
        return Response({"n": calls}, status=200)

    with_idempotency(_request("shared-key", admin_user), "endpoint-a", handler)
    with_idempotency(_request("shared-key", admin_user), "endpoint-b", handler)
    assert calls == 2


def test_same_key_different_user_does_not_collide(admin_user, employee):
    calls = 0

    def handler():
        nonlocal calls
        calls += 1
        return Response({"n": calls}, status=200)

    with_idempotency(_request("shared-key", admin_user), "test-ep", handler)
    with_idempotency(_request("shared-key", employee), "test-ep", handler)
    assert calls == 2


def test_error_response_is_also_replayed_verbatim(admin_user):
    def handler():
        return Response({"code": "invalid", "message": "だめ", "field_errors": {}}, status=400)

    res1 = with_idempotency(_request("k1", admin_user), "test-ep", handler)
    res2 = with_idempotency(_request("k1", admin_user), "test-ep", handler)
    assert res1.status_code == res2.status_code == 400
    assert res2.data == {"code": "invalid", "message": "だめ", "field_errors": {}}


# --- API統合: 打刻 ---

def test_punch_with_same_idempotency_key_does_not_double_clock_in(client, employee):
    from apps.attendance.models import TimeRecord

    client.force_login(employee)
    headers = {"HTTP_IDEMPOTENCY_KEY": "punch-key-1"}
    res1 = client.post(reverse("attendance-punch"), {"action": "in"}, content_type="application/json", **headers)
    assert res1.status_code == 204

    # ネットワーク再送を想定して同じキーで再送 → 実処理は再実行されない
    res2 = client.post(reverse("attendance-punch"), {"action": "in"}, content_type="application/json", **headers)
    assert res2.status_code == 204

    records = TimeRecord.objects.filter(user=employee)
    assert records.count() == 1
    assert records.first().clock_in_at is not None

    assert IdempotencyKey.objects.filter(key="punch-key-1", endpoint="attendance-punch").exists()


def test_punch_without_idempotency_key_processes_normally(client, employee):
    client.force_login(employee)
    res = client.post(reverse("attendance-punch"), {"action": "in"}, content_type="application/json")
    assert res.status_code == 204
    assert not IdempotencyKey.objects.exists()


# --- API統合: 請求書一括生成 ---

@pytest.fixture
def contractor(db):
    c = Contractor.objects.create(
        name="テスト外注先", tax_category="taxable", withholding_target=True,
        closing_day=31, payment_month_offset=1, payment_day=10,
    )
    ContractorRate.objects.create(contractor=c, rate_type="hourly", rate_amount=Decimal("4500"), effective_from=date(2024, 1, 1))
    return c


def test_generate_invoices_with_same_idempotency_key_does_not_create_duplicates(client, admin_user, contractor):
    from apps.billing.models import Invoice

    ContractorWorkRecord.objects.create(contractor=contractor, year_month="2026-07", hours=Decimal("40"))
    client.force_login(admin_user)
    headers = {"HTTP_IDEMPOTENCY_KEY": "gen-key-1"}

    res1 = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json", **headers)
    assert res1.json()["created_count"] == 1

    res2 = client.post(reverse("invoices-generate"), {"year_month": "2026-07"}, content_type="application/json", **headers)
    assert res2.json() == res1.json()

    assert Invoice.objects.filter(period_end__year=2026, period_end__month=7).count() == 1
