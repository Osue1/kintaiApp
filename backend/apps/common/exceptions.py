"""API のエラー形式を { code, message, field_errors } に統一する（設計書 第10.1章）。

message はそのまま画面に出せる日本語にする。
"""
from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

DEFAULT_MESSAGES = {
    400: "入力内容を確認してください。",
    401: "ログインが必要です。",
    403: "この操作を行う権限がありません。",
    404: "対象が見つかりません。",
    409: "他の操作と競合しました。画面を更新してやり直してください。",
    429: "リクエストが多すぎます。しばらく待ってからお試しください。",
    500: "サーバー側で問題が発生しました。",
}


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    status_code = response.status_code
    detail = response.data
    field_errors: dict[str, list[str]] = {}
    message = DEFAULT_MESSAGES.get(status_code, "処理できませんでした。")

    if isinstance(detail, dict):
        if "detail" in detail:
            message = str(detail["detail"])
        else:
            field_errors = {
                key: [str(v) for v in (value if isinstance(value, list) else [value])]
                for key, value in detail.items()
            }
    elif isinstance(detail, list):
        message = " ".join(str(item) for item in detail)

    response.data = {
        "code": getattr(exc, "default_code", "error"),
        "message": message,
        "field_errors": field_errors,
    }
    return response
