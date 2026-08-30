"""パスワード再設定のセルフサービスフロー。"""
import re
from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PasswordResetToken

pytestmark = pytest.mark.django_db

RESET_URL_BASE = "http://localhost:5173/password-reset"


def _extract_token_from_mail(body: str) -> str:
    match = re.search(r"[?&]token=([\w-]+)", body)
    assert match, f"メール本文からトークンを取り出せませんでした: {body}"
    return match.group(1)


def test_request_with_existing_email_sends_reset_email(client, employee):
    res = client.post(
        reverse("password-reset-request"),
        {"email": employee.email, "reset_url_base": RESET_URL_BASE},
        content_type="application/json",
    )
    assert res.status_code == 204
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [employee.email]
    assert RESET_URL_BASE in mail.outbox[0].body
    assert PasswordResetToken.objects.filter(user=employee).count() == 1


def test_request_with_unknown_email_is_silently_ignored(client):
    """メールアドレスの在不在で挙動を変えない（列挙攻撃対策）。存在しなくても204・メール送信なし。"""
    res = client.post(
        reverse("password-reset-request"),
        {"email": "nobody@example.com", "reset_url_base": RESET_URL_BASE},
        content_type="application/json",
    )
    assert res.status_code == 204
    assert len(mail.outbox) == 0
    assert not PasswordResetToken.objects.exists()


def test_confirm_with_valid_token_changes_password(client, employee):
    client.post(
        reverse("password-reset-request"),
        {"email": employee.email, "reset_url_base": RESET_URL_BASE},
        content_type="application/json",
    )
    token = _extract_token_from_mail(mail.outbox[0].body)

    res = client.post(
        reverse("password-reset-confirm"),
        {"token": token, "password": "brand-new-password-123"},
        content_type="application/json",
    )
    assert res.status_code == 204

    # 新パスワードでログインでき、旧パスワードではログインできないこと
    res = client.post(
        reverse("login"),
        {"email": employee.email, "password": "brand-new-password-123"},
        content_type="application/json",
    )
    assert res.status_code == 200

    client.post(reverse("logout"))
    res = client.post(
        reverse("login"),
        {"email": employee.email, "password": "correct-horse-battery"},
        content_type="application/json",
    )
    assert res.status_code == 401


def test_confirm_rejects_unknown_token(client):
    res = client.post(
        reverse("password-reset-confirm"),
        {"token": "does-not-exist", "password": "brand-new-password-123"},
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_token"


def test_confirm_rejects_expired_token(client, employee):
    client.post(
        reverse("password-reset-request"),
        {"email": employee.email, "reset_url_base": RESET_URL_BASE},
        content_type="application/json",
    )
    token = _extract_token_from_mail(mail.outbox[0].body)
    PasswordResetToken.objects.filter(user=employee).update(expires_at=timezone.now() - timedelta(minutes=1))

    res = client.post(
        reverse("password-reset-confirm"),
        {"token": token, "password": "brand-new-password-123"},
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_token"


def test_confirm_rejects_already_used_token(client, employee):
    client.post(
        reverse("password-reset-request"),
        {"email": employee.email, "reset_url_base": RESET_URL_BASE},
        content_type="application/json",
    )
    token = _extract_token_from_mail(mail.outbox[0].body)

    res1 = client.post(
        reverse("password-reset-confirm"),
        {"token": token, "password": "brand-new-password-123"},
        content_type="application/json",
    )
    assert res1.status_code == 204

    res2 = client.post(
        reverse("password-reset-confirm"),
        {"token": token, "password": "another-password-456"},
        content_type="application/json",
    )
    assert res2.status_code == 400
    assert res2.json()["code"] == "invalid_token"


def test_confirm_rejects_weak_password(client, employee):
    client.post(
        reverse("password-reset-request"),
        {"email": employee.email, "reset_url_base": RESET_URL_BASE},
        content_type="application/json",
    )
    token = _extract_token_from_mail(mail.outbox[0].body)

    res = client.post(
        reverse("password-reset-confirm"),
        {"token": token, "password": "12345"},
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_token"


def test_confirming_one_token_invalidates_other_outstanding_tokens_for_same_user(client, employee):
    """境界値: 同じユーザーが2回リクエストした場合、古い方のリンクは新しい方を使った時点で無効化される。"""
    client.post(
        reverse("password-reset-request"),
        {"email": employee.email, "reset_url_base": RESET_URL_BASE},
        content_type="application/json",
    )
    old_token = _extract_token_from_mail(mail.outbox[0].body)

    client.post(
        reverse("password-reset-request"),
        {"email": employee.email, "reset_url_base": RESET_URL_BASE},
        content_type="application/json",
    )
    new_token = _extract_token_from_mail(mail.outbox[1].body)

    res = client.post(
        reverse("password-reset-confirm"),
        {"token": new_token, "password": "brand-new-password-123"},
        content_type="application/json",
    )
    assert res.status_code == 204

    res = client.post(
        reverse("password-reset-confirm"),
        {"token": old_token, "password": "yet-another-password-789"},
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_token"
