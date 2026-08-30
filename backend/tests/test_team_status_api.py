"""他社員の出勤状況（グループ既定・全社員切替）のテスト。"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, Team
from apps.attendance.services import records as record_service

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def team_a(db):
    return Team.objects.create(name="開発チーム")


@pytest.fixture
def team_b(db):
    return Team.objects.create(name="営業チーム")


def test_default_scope_shows_only_same_team(client, work_pattern, team_a, team_b):
    alice = User.objects.create_user(email="alice@example.com", password="x", name="Alice", role=Role.EMPLOYEE, team=team_a)
    User.objects.create_user(email="bob@example.com", password="x", name="Bob", role=Role.EMPLOYEE, team=team_a)
    User.objects.create_user(email="carol@example.com", password="x", name="Carol", role=Role.EMPLOYEE, team=team_b)

    client.force_login(alice)
    res = client.get(reverse("attendance-status"))
    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == "team"
    assert body["fallback_to_all"] is False
    names = {m["name"] for m in body["members"]}
    assert names == {"Alice", "Bob"}


def test_scope_all_shows_every_active_employee(client, team_a, team_b):
    alice = User.objects.create_user(email="alice@example.com", password="x", name="Alice", role=Role.EMPLOYEE, team=team_a)
    User.objects.create_user(email="carol@example.com", password="x", name="Carol", role=Role.EMPLOYEE, team=team_b)

    client.force_login(alice)
    res = client.get(reverse("attendance-status"), {"scope": "all"})
    names = {m["name"] for m in res.json()["members"]}
    assert names == {"Alice", "Carol"}


def test_no_team_falls_back_to_all_with_flag(client, team_a):
    solo = User.objects.create_user(email="solo@example.com", password="x", name="Solo", role=Role.EMPLOYEE, team=None)
    User.objects.create_user(email="alice@example.com", password="x", name="Alice", role=Role.EMPLOYEE, team=team_a)

    client.force_login(solo)
    res = client.get(reverse("attendance-status"))
    body = res.json()
    assert body["scope"] == "all"
    assert body["fallback_to_all"] is True
    assert {m["name"] for m in body["members"]} == {"Solo", "Alice"}


def test_punch_state_and_times_are_reflected(client, team_a):
    alice = User.objects.create_user(email="alice@example.com", password="x", name="Alice", role=Role.EMPLOYEE, team=team_a)
    record_service.clock_in(alice, at=timezone.now())

    client.force_login(alice)
    res = client.get(reverse("attendance-status"))
    member = res.json()["members"][0]
    assert member["state"] == "working"
    assert member["clock_in_at"] is not None
    assert member["clock_out_at"] is None


def test_inactive_employees_are_excluded(client, team_a):
    alice = User.objects.create_user(email="alice@example.com", password="x", name="Alice", role=Role.EMPLOYEE, team=team_a)
    User.objects.create_user(email="retired@example.com", password="x", name="Retired", role=Role.EMPLOYEE, team=team_a, is_active=False)

    client.force_login(alice)
    res = client.get(reverse("attendance-status"))
    names = {m["name"] for m in res.json()["members"]}
    assert names == {"Alice"}
