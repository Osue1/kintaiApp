"""従業員管理APIのテスト。"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_admin_can_list_and_create_employee(client, admin_user, work_pattern):
    client.force_login(admin_user)
    res = client.get(reverse("employees-list"))
    assert res.status_code == 200
    assert any(e["email"] == admin_user.email for e in res.json())

    res = client.post(
        reverse("employees-list"),
        {
            "email": "new-hire@example.com",
            "name": "新人太郎",
            "password": "correct-horse-battery",
            "role": "employee",
            "hire_date": "2026-04-01",
            "work_pattern": work_pattern.id,
        },
        content_type="application/json",
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "new-hire@example.com"
    assert body["work_pattern_name"] == work_pattern.name
    assert body["is_admin"] is False


def test_create_employee_rejects_duplicate_email(client, admin_user, employee):
    client.force_login(admin_user)
    res = client.post(
        reverse("employees-list"),
        {"email": employee.email, "name": "重複太郎", "password": "correct-horse-battery"},
        content_type="application/json",
    )
    assert res.status_code == 400
    assert "email" in res.json()["field_errors"]


def test_create_employee_rejects_weak_password(client, admin_user):
    client.force_login(admin_user)
    res = client.post(
        reverse("employees-list"),
        {"email": "weak@example.com", "name": "弱いパスワード", "password": "12345"},
        content_type="application/json",
    )
    assert res.status_code == 400
    assert "password" in res.json()["field_errors"]


def test_admin_can_update_employee(client, admin_user, employee, work_pattern):
    client.force_login(admin_user)
    res = client.patch(
        reverse("employees-detail", args=[employee.id]),
        {"work_pattern": work_pattern.id, "hire_date": "2025-01-01"},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json()["hire_date"] == "2025-01-01"


def test_admin_cannot_deactivate_self(client, admin_user):
    client.force_login(admin_user)
    res = client.patch(
        reverse("employees-detail", args=[admin_user.id]),
        {"is_active": False},
        content_type="application/json",
    )
    assert res.status_code == 400


def test_non_admin_cannot_access_employees(client, employee):
    client.force_login(employee)
    assert client.get(reverse("employees-list")).status_code == 403
