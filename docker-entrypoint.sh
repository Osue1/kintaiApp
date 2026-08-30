#!/bin/sh
# 無料枠のRenderにはPre-Deploy Command機能が無い（有料プラン限定）ため、
# コンテナ起動のたびにマイグレーション適用〜マスタ投入を行う。
# 無料枠は水平スケールしない（インスタンスは常に1つ）ため、複数インスタンスが
# 同時に migrate を叩き合う心配はない。インスタンスを増やす構成に変える場合は
# ここではなく別のリリースステップに移すこと。
set -e

echo "[entrypoint] マイグレーションを適用します..."
python manage.py migrate --noinput

echo "[entrypoint] 会社設定・勤務体系・休暇種類等の初期マスタを投入します（冪等）..."
python manage.py seed_initial_data

# 本番データ向けではない（社員・打刻履歴・休暇消化等のサンプルデータ）。
# 「まずは画面を触ってみたい」という無料お試し用途のときだけ、環境変数
# SEED_DEMO_DATA=true を設定して有効化する。常時オンにはしないこと。
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  echo "[entrypoint] SEED_DEMO_DATA=true: デモデータ（社員・外注先・打刻履歴等）を投入します"
  echo "[entrypoint] 注意: これは本番データ運用には使わないでください"
  python manage.py create_demo_data
fi

echo "[entrypoint] gunicornを起動します（port=${PORT:-8000}）"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 60
