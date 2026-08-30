"""ヘルスチェック・SPA配信。

集約監視がこれを定期的に叩き、想定バージョンと違う環境を検知する（追補 第7.3章）。
"""
import os

from django.conf import settings
from django.db import connection
from django.http import HttpResponse, JsonResponse

APP_VERSION = os.environ.get("APP_VERSION", "dev")


def _latest_migration() -> str | None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT app, name FROM django_migrations ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
        return f"{row[0]}.{row[1]}" if row else None
    except Exception:  # noqa: BLE001 - 監視用途なので握りつぶして status に出す
        return None


def health(request) -> JsonResponse:
    latest = _latest_migration()
    return JsonResponse(
        {
            "status": "ok" if latest is not None else "degraded",
            "version": APP_VERSION,
            "latest_migration": latest,
        },
        status=200 if latest is not None else 503,
    )


def spa_index(request) -> HttpResponse:
    """フロントエンド（Vue SPA）の index.html を返す。

    無料枠のクラウド1台だけで動かす構成（Docker で frontend のビルド成果物を
    バックエンドと同梱する）では、本来 GCP 本番のロードバランサが担っている
    「/api 以外はフロントエンドへ」の振り分けを Django 自身が行う必要がある
    （config/urls.py の catch-all から呼ばれる）。history モードのルータでは
    "/mypage" 等を直接開いたり再読み込みしたりしても index.html が返らないと
    404 になってしまうため、既知のプレフィックス以外の全パスをここで拾う。

    index.html は同じ内容でもデプロイの度に参照するハッシュ付きアセット名が
    変わるため、静的アセット（/static/配下）とは違い長期キャッシュしてはいけない。
    """
    index_path = settings.FRONTEND_INDEX_HTML
    if not index_path.is_file():
        # フロントエンドを同梱していない環境（バックエンド単体のCloud Run等）。
        # ここに来ること自体が想定外だが、原因が分かるメッセージを返す。
        return HttpResponse(
            "フロントエンドの配信ファイルが見つかりません（FRONTEND_DIST_DIR未設定、"
            "またはビルド未実施の可能性があります）。",
            status=404,
            content_type="text/plain; charset=utf-8",
        )
    return HttpResponse(
        index_path.read_text(encoding="utf-8"),
        content_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )
