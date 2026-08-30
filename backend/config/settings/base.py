"""全環境で共通の設定。環境ごとの差分は dev.py / prod.py と環境変数で与える。"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Docker では compose.yaml の env_file が環境変数を渡す。ローカルで直接 manage.py を
# 動かすときのために .env があれば読む（無くても既定値で起動できる）。
_dotenv = BASE_DIR / ".env"
if _dotenv.exists():
    environ.Env.read_env(str(_dotenv))

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    TIME_ZONE=(str, "Asia/Tokyo"),
)

# 開発と CI で動くよう既定値を持つ。prod.py で既定値のままなら起動を止める。
INSECURE_DEV_SECRET_KEY = "insecure-dev-key-change-me"
SECRET_KEY = env("DJANGO_SECRET_KEY", default=INSECURE_DEV_SECRET_KEY)
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

# メール本文のリンクや署名付きURLはここから組み立てる。
# リクエストの Host を使うと、併設サブドメイン経由でアクセスされた日だけ
# URL が変わってしまうため（追補 第5.5章）。
PRIMARY_ORIGIN = env("DJANGO_PRIMARY_ORIGIN", default="http://localhost:5173")

# サイト全体にかけるHTTP Basic認証（apps/common/middleware.py）。両方設定した
# 環境でだけ有効になる。アプリ内のログイン機能とは別レイヤーの入口の防御で、
# 無料枠で公開したデモ環境などを検索エンジンや偶然のアクセスから塞ぐ用途。
BASIC_AUTH_USER = env("BASIC_AUTH_USER", default="")
BASIC_AUTH_PASSWORD = env("BASIC_AUTH_PASSWORD", default="")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    # "axes" ではなくこちらを登録して、管理画面の表示だけ日本語化する
    # （apps/common/axes_app_config.py 参照。モデル・機能はaxes本体のまま）。
    "apps.common.axes_app_config.LocalizedAxesConfig",
    "apps.common",
    "apps.accounts",
    "apps.attendance",
    "apps.leave",
    "apps.compliance",
    "apps.contractors",
    "apps.billing",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # 静的ファイルより前に置き、Basic認証が有効な環境ではCSS/JSも含めて
    # 一番手前で塞ぐ（BASIC_AUTH_USER/PASSWORD未設定なら何もしない）。
    "apps.common.middleware.BasicAuthMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://kintai:kintai@localhost:5432/kintai"
    )
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    # django-axes は先頭に置く必要がある
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# 5回失敗で15分ロック（設計書 第3.1章）
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.25
AXES_LOCKOUT_PARAMETERS = ["username"]

LANGUAGE_CODE = "ja"
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# 本番は Cloud Storage（設計書 第3章）。ローカルはファイルシステムに保存する。
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# フロントエンド（Vue SPA）のビルド成果物の場所。
#
# GCP本番（infra/README.md）ではロードバランサがフロントエンドをCloud Storageから
# 直接配信するため、Django側はここを参照しない。一方、無料枠のクラウド1台だけで
# 動かす構成ではバックエンドと同梱してDjango自身に配信させる（apps/common/views.py
# の spa_index）。ディレクトリが無い環境（バックエンド単体のCloud Run等）でも
# collectstatic やアプリ起動自体は落とさず、フロントエンド関連の配信だけが
# 無効になるようにする。
FRONTEND_DIST_DIR = Path(env("FRONTEND_DIST_DIR", default=str(BASE_DIR.parent / "frontend" / "dist")))
FRONTEND_INDEX_HTML = FRONTEND_DIST_DIR / "index.html"
_frontend_assets_dir = FRONTEND_DIST_DIR / "assets"
# タプル形式でプレフィックス"assets/"を保ったまま取り込む。素の文字列パスで
# 指定すると中身がSTATIC_URL直下に平置きされてしまい、Viteが埋め込んだ
# "/static/assets/xxx" というURL（vite.config.ts の base: '/static/'）と
# 実際の配信パスがズレてしまう（例: フォントファイルが404になる）。
STATICFILES_DIRS = [("assets", _frontend_assets_dir)] if _frontend_assets_dir.is_dir() else []

DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="noreply@kintai.example.com")

# SMTP接続先。dev.py が EMAIL_BACKEND をコンソール出力に差し替えているため、
# 開発環境ではここは使われない。本番（prod.py）は明示的な差し替えをせず
# Djangoの既定バックエンド（SMTP）のまま、ここで設定した接続先を使う。
# 未設定のままだと localhost:25 に繋ぎに行って失敗する（パスワードリセット
# メール・通知メールが送れない）ので、無料枠で試す場合も必ず設定すること。
EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # SPA と同一オリジンで配信するためセッション認証を使う（設計書 第3.1章）
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "勤怠管理・外注請求システム API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# サブドメイン間でセッションを共有しないため Domain は設定しない
SESSION_COOKIE_DOMAIN = None

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
