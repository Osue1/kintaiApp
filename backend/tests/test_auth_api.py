"""認証APIと権限のテスト。"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_login_returns_me(client, employee):
    res = client.post(
        reverse("login"),
        {"email": employee.email, "password": "correct-horse-battery"},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json()["email"] == employee.email
    assert res.json()["is_admin"] is False


def test_login_with_wrong_password_returns_japanese_message(client, employee):
    res = client.post(
        reverse("login"),
        {"email": employee.email, "password": "wrong-password-here"},
        content_type="application/json",
    )
    assert res.status_code == 401
    body = res.json()
    assert body["code"] == "invalid_credentials"
    assert "メールアドレスまたはパスワード" in body["message"]


def test_me_requires_authentication(client):
    res = client.get(reverse("me"))
    assert res.status_code in (401, 403)


def test_me_includes_company(client, employee, company):
    client.force_login(employee)
    res = client.get(reverse("me"))
    assert res.status_code == 200
    assert res.json()["company"]["name"] == "株式会社テスト"


def test_admin_flag_is_exposed(client, admin_user):
    client.force_login(admin_user)
    assert client.get(reverse("me")).json()["is_admin"] is True


def test_logout_clears_session(client, employee):
    client.force_login(employee)
    assert client.post(reverse("logout")).status_code == 204
    assert client.get(reverse("me")).status_code in (401, 403)


def test_error_format_is_uniform(client):
    res = client.post(reverse("login"), {"email": "not-an-email"}, content_type="application/json")
    assert res.status_code == 400
    body = res.json()
    assert set(body) == {"code", "message", "field_errors"}
    assert "email" in body["field_errors"]
