"""サイト全体にかけるHTTP Basic認証ミドルウェアの試験（apps/common/middleware.py）。

無料枠で公開したデモ環境を検索エンジンや偶然のアクセスから塞ぐための、
アプリ内ログインとは別レイヤーの入口防御。BASIC_AUTH_USER/PASSWORD
両方が設定された環境でだけ有効になる。
"""
import base64

import pytest

pytestmark = pytest.mark.django_db


def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def test_disabled_by_default_when_credentials_not_configured(client, settings):
    settings.BASIC_AUTH_USER = ""
    settings.BASIC_AUTH_PASSWORD = ""
    res = client.get("/healthz")
    assert res.status_code == 200


def test_blocks_request_without_credentials_when_enabled(client, settings):
    settings.BASIC_AUTH_USER = "demo"
    settings.BASIC_AUTH_PASSWORD = "secret-pass"
    res = client.get("/api/v1/auth/csrf")
    assert res.status_code == 401
    assert res["WWW-Authenticate"].startswith("Basic")


def test_allows_request_with_correct_credentials(client, settings):
    settings.BASIC_AUTH_USER = "demo"
    settings.BASIC_AUTH_PASSWORD = "secret-pass"
    res = client.get(
        "/api/v1/auth/csrf", HTTP_AUTHORIZATION=_basic_auth_header("demo", "secret-pass")
    )
    assert res.status_code == 204


def test_blocks_request_with_wrong_password(client, settings):
    settings.BASIC_AUTH_USER = "demo"
    settings.BASIC_AUTH_PASSWORD = "secret-pass"
    res = client.get(
        "/api/v1/auth/csrf", HTTP_AUTHORIZATION=_basic_auth_header("demo", "wrong")
    )
    assert res.status_code == 401


def test_blocks_request_with_malformed_authorization_header(client, settings):
    """base64として不正な値が来てもクラッシュせず401を返すこと。"""
    settings.BASIC_AUTH_USER = "demo"
    settings.BASIC_AUTH_PASSWORD = "secret-pass"
    res = client.get("/api/v1/auth/csrf", HTTP_AUTHORIZATION="Basic not-valid-base64!!!")
    assert res.status_code == 401


def test_healthz_is_exempt_even_when_enabled(client, settings):
    """Renderのヘルスチェックは資格情報を送ってこないため、healthzだけは素通しする。"""
    settings.BASIC_AUTH_USER = "demo"
    settings.BASIC_AUTH_PASSWORD = "secret-pass"
    res = client.get("/healthz")
    assert res.status_code in (200, 503)  # DB接続状況次第。401にはならないことが重要。


def test_disabled_when_only_username_configured(client, settings):
    """片方だけ設定されている中途半端な状態では無効化する（誤設定でロックアウトしない）。"""
    settings.BASIC_AUTH_USER = "demo"
    settings.BASIC_AUTH_PASSWORD = ""
    res = client.get("/api/v1/auth/csrf")
    assert res.status_code == 200 or res.status_code == 204
