"""アプリ全体にHTTP Basic認証をかけるミドルウェア。

無料枠のクラウド1台に公開したデモ環境など、「検索エンジンや偶然のアクセスから
まず塞いでおきたいが、本格的なユーザー管理を作るほどではない」場面向け。
アプリ内のログイン機能（セッション認証）とは別レイヤーで、リクエストが
アプリに届く前の入口をもう1段防御する。

BASIC_AUTH_USER / BASIC_AUTH_PASSWORD が両方とも設定されている環境でだけ
有効になる。片方でも空なら何もしない（ローカル開発や、Basic認証を使わない
環境に影響しない）。
"""
import base64
import binascii
import hmac

from django.conf import settings
from django.http import HttpResponse

# Render等のヘルスチェックはBasic認証の資格情報を送ってこないため、ここだけは
# 素通しする（塞ぐとヘルスチェックが常に401になり、サービスが不健全と
# 誤判定されてしまう）。
_EXEMPT_PATHS = {"/healthz"}


class BasicAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._enabled() and request.path not in _EXEMPT_PATHS:
            denied = self._check(request)
            if denied is not None:
                return denied
        return self.get_response(request)

    @staticmethod
    def _enabled() -> bool:
        return bool(settings.BASIC_AUTH_USER and settings.BASIC_AUTH_PASSWORD)

    @staticmethod
    def _check(request) -> HttpResponse | None:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        scheme, _, credentials = header.partition(" ")
        if scheme.lower() == "basic" and credentials:
            try:
                decoded = base64.b64decode(credentials).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                decoded = ""
            username, _, password = decoded.partition(":")
            # タイミング攻撃対策でhmac.compare_digestを使う（==だと文字列の
            # 一致箇所の長さで比較時間が変わり、総当たりのヒントになり得る）。
            user_ok = hmac.compare_digest(username, settings.BASIC_AUTH_USER)
            pass_ok = hmac.compare_digest(password, settings.BASIC_AUTH_PASSWORD)
            if user_ok and pass_ok:
                return None

        response = HttpResponse(
            "認証が必要です。",
            status=401,
            content_type="text/plain; charset=utf-8",
        )
        response["WWW-Authenticate"] = 'Basic realm="kintai-app", charset="UTF-8"'
        return response
