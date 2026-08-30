from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "backend", "testserver"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://localhost:8000"]

# 本番は Amazon SES（設計書 第2.5章）。ローカルはコンソール出力で代替し、
# EMAIL_BACKEND の差し替えだけで本番設定に移行できるようにする。
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
