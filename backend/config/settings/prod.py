from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

if SECRET_KEY == INSECURE_DEV_SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured(  # noqa: F405
        "本番環境では DJANGO_SECRET_KEY を設定してください。"
    )

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS に includeSubDomains は付けない。
# 顧客ドメイン配下に証明書を張るため、付けると顧客の他サブドメイン全部に
# HTTPS を強制してしまう（追補 第5.5章）。
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
