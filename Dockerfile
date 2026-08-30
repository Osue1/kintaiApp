# 無料枠のクラウド1台（例: Render の無料 Web Service）にフロントエンドと
# バックエンドをまとめてデプロイするための結合Dockerfile。
#
# GCP本番（infra/README.md、backend/Dockerfile）はロードバランサがフロントエンドを
# Cloud Storageから直接配信し、Cloud RunにはバックエンドAPIだけを乗せる構成のため、
# backend/Dockerfile はあえてフロントエンドを含めていない。このファイルはそれとは
# 別に、「無料枠のサーバ1台だけでまず試す」ための構成として追加したもの。
#
# ビルドコンテキストはリポジトリルート（backend/ と frontend/ の両方を参照するため）。
#   docker build -f Dockerfile -t kintai-app .
#
# Render にデプロイする場合:
#   - Dockerfile Path: Dockerfile
#   - Docker Build Context Directory: .  （リポジトリルート）

# ---- Stage 1: フロントエンド（Vue SPA）をビルド ----
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
# vite.config.ts の base: '/static/' により、ビルド後のJS/CSSはDjangoの
# STATIC_URL配下を参照するようになる（バックエンド側で同梱配信するため）。
RUN npm run build

# ---- Stage 2: バックエンド（Django）+ 同梱フロントエンド ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# WeasyPrint（PDF生成）が必要とするライブラリ。backend/Dockerfile と同じ一式。
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
        libffi-dev shared-mime-info fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist /app/frontend_dist
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ARG APP_VERSION=dev
# manage.py はDJANGO_SETTINGS_MODULE未設定だとconfig.settings.devにフォールバックする
# （backend/manage.py参照）。ここで既定を本番設定にしておかないと、
# docker-entrypoint.sh 内のmigrate/seedがdev設定（本番シークレット無しの既定値）で
# 実行されてしまう。Render側で別途上書き設定する必要はない（したい場合は上書き可）。
ENV APP_VERSION=${APP_VERSION} \
    FRONTEND_DIST_DIR=/app/frontend_dist \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# collectstatic は秘密情報を必要としない dev 設定で行う（本番設定は
# DJANGO_SECRET_KEY 等がビルド時に無いと ImproperlyConfigured で落ちるため）。
# フロントエンドの成果物は FRONTEND_DIST_DIR 経由で assets/ プレフィックス付き
# で取り込まれる（config/settings/base.py の STATICFILES_DIRS を参照）。
RUN python manage.py collectstatic --noinput --settings=config.settings.dev

EXPOSE 8000
# 起動時にマイグレーション適用〜gunicorn起動までを行う（無料枠のRenderには
# Pre-Deploy Command機能が無いため。docker-entrypoint.sh 参照）。
# 環境変数 PORT はRender等のPaaSがリッスンすべきポートを指示してくる。
ENTRYPOINT ["/app/docker-entrypoint.sh"]
