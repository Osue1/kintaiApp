#!/usr/bin/env bash
# Docker を使わずローカルで動かすための起動・停止スクリプト。
#
#   scripts/local-dev.sh up          # PostgreSQL・Django・Vite をまとめて起動
#   scripts/local-dev.sh down        # まとめて停止
#   scripts/local-dev.sh status      # 起動状況を表示
#   scripts/local-dev.sh logs [名前]  # ログを追う（django / vite / postgres、省略時は django）
#   scripts/local-dev.sh seed-demo   # デモデータ（社員・外注先・打刻履歴等）を投入
#
# 前提: Homebrew, postgresql@16, Python 3.12+, Node.js 22
#   brew install postgresql@16 cairo pango gdk-pixbuf harfbuzz
#
# 起動したプロセスの PID・ログは repo/.local 配下に置く。Vite をユーザーが別ターミナルで
# 手動起動している場合は検知してスキップし、誤って人のセッションを止めないようにする。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.local/run"
LOG_DIR="$ROOT_DIR/.local/log"

BACKEND_PORT=8000
FRONTEND_PORT=5173
DB_NAME=kintai
DB_ROLE=kintai
DB_PASSWORD=kintai

mkdir -p "$RUN_DIR" "$LOG_DIR"

# ---- 共通ヘルパー ----

log() { printf '\033[36m[local-dev]\033[0m %s\n' "$1"; }
warn() { printf '\033[33m[local-dev]\033[0m %s\n' "$1"; }
err() { printf '\033[31m[local-dev]\033[0m %s\n' "$1" >&2; }

port_in_use() {
  lsof -i ":$1" -sTCP:LISTEN >/dev/null 2>&1
}

pid_alive() {
  [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null
}

require_brew_formula() {
  if ! brew --prefix "$1" >/dev/null 2>&1; then
    err "$1 が見つかりません。'brew install $1' を実行してください。"
    exit 1
  fi
}

# ---- PostgreSQL ----

pg_bin() { echo "$(brew --prefix postgresql@16)/bin"; }
pg_data() { echo "$(brew --prefix)/var/postgresql@16"; }

pg_start() {
  require_brew_formula postgresql@16
  local data_dir; data_dir="$(pg_data)"
  if [ ! -d "$data_dir" ]; then
    log "PostgreSQL のデータディレクトリを初期化します: $data_dir"
    "$(pg_bin)/initdb" --locale=C -E UTF8 -D "$data_dir" >"$LOG_DIR/postgres-initdb.log" 2>&1
  fi

  if "$(pg_bin)/pg_ctl" -D "$data_dir" status >/dev/null 2>&1; then
    log "PostgreSQL は起動済みです。"
  else
    log "PostgreSQL を起動します..."
    "$(pg_bin)/pg_ctl" -D "$data_dir" -l "$LOG_DIR/postgres.log" start
  fi

  for _ in $(seq 1 20); do
    if "$(pg_bin)/pg_isready" -q >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done

  local psql="$(pg_bin)/psql"
  local role_exists
  role_exists=$("$psql" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_ROLE'" -d postgres 2>/dev/null || true)
  if [ "$role_exists" != "1" ]; then
    log "ロール $DB_ROLE を作成します。"
    "$psql" -d postgres -c "CREATE ROLE $DB_ROLE LOGIN PASSWORD '$DB_PASSWORD' CREATEDB;" >/dev/null
  fi
  if ! "$psql" -lqt | cut -d '|' -f 1 | grep -qw "$DB_NAME"; then
    log "データベース $DB_NAME を作成します。"
    "$(pg_bin)/createdb" -O "$DB_ROLE" "$DB_NAME"
  fi
}

pg_stop() {
  local data_dir; data_dir="$(pg_data)"
  if [ -d "$data_dir" ] && "$(pg_bin)/pg_ctl" -D "$data_dir" status >/dev/null 2>&1; then
    log "PostgreSQL を停止します..."
    "$(pg_bin)/pg_ctl" -D "$data_dir" stop -m fast
  else
    log "PostgreSQL は起動していません。"
  fi
}

pg_status() {
  local data_dir; data_dir="$(pg_data)"
  if [ -d "$data_dir" ] && "$(pg_bin)/pg_ctl" -D "$data_dir" status >/dev/null 2>&1; then
    echo "PostgreSQL : 起動中 (port 5432)"
  else
    echo "PostgreSQL : 停止"
  fi
}

# ---- Django backend ----

backend_env_setup() {
  if [ ! -d "$BACKEND_DIR/.venv" ]; then
    log "Python 仮想環境を作成します..."
    python3 -m venv "$BACKEND_DIR/.venv"
    "$BACKEND_DIR/.venv/bin/pip" install --upgrade pip -q
    "$BACKEND_DIR/.venv/bin/pip" install -q \
      "Django>=5.1,<5.2" "djangorestframework>=3.15,<3.16" "drf-spectacular>=0.27,<0.28" \
      "psycopg[binary]>=3.2,<3.3" "django-environ>=0.11,<0.12" "django-axes>=6.5,<7.0" \
      "gunicorn>=23.0" "whitenoise>=6.7" "WeasyPrint>=62.0" "jpholiday>=0.1.9" \
      "pytest>=8.3" "pytest-django>=4.9" "pytest-cov>=5.0" "freezegun>=1.5" "ruff>=0.6"
  fi
  if [ ! -f "$BACKEND_DIR/.env" ]; then
    log "backend/.env を作成します。"
    cat > "$BACKEND_DIR/.env" <<EOF
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=dev-only-change-me
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://localhost:8000
DATABASE_URL=postgres://$DB_ROLE:$DB_PASSWORD@localhost:5432/$DB_NAME
TIME_ZONE=Asia/Tokyo
EOF
  fi
}

backend_start() {
  backend_env_setup
  local pid_file="$RUN_DIR/django.pid"
  if pid_alive "$pid_file"; then
    log "Django は起動済みです (PID $(cat "$pid_file"))。"
    return
  fi
  if port_in_use "$BACKEND_PORT"; then
    warn "port $BACKEND_PORT は既に使用中です。このスクリプト外で起動済みとみなしスキップします。"
    return
  fi

  ( cd "$BACKEND_DIR" && source .venv/bin/activate && python3 manage.py migrate --noinput ) \
    >"$LOG_DIR/django-migrate.log" 2>&1 || { err "migrate に失敗しました。$LOG_DIR/django-migrate.log を確認してください。"; exit 1; }
  ( cd "$BACKEND_DIR" && source .venv/bin/activate && python3 manage.py seed_initial_data ) \
    >>"$LOG_DIR/django-migrate.log" 2>&1 || true

  log "Django を起動します (http://localhost:$BACKEND_PORT)..."
  ( cd "$BACKEND_DIR" && source .venv/bin/activate && exec python3 manage.py runserver "$BACKEND_PORT" ) \
    >"$LOG_DIR/django.log" 2>&1 &
  echo $! > "$pid_file"
  disown
}

backend_stop() {
  local pid_file="$RUN_DIR/django.pid"
  if pid_alive "$pid_file"; then
    log "Django を停止します..."
    pkill -P "$(cat "$pid_file")" 2>/dev/null || true
    kill "$(cat "$pid_file")" 2>/dev/null || true
  else
    log "Django（このスクリプトが起動したもの）は動いていません。"
  fi
  rm -f "$pid_file"
}

# ---- Vite frontend ----

frontend_start() {
  local pid_file="$RUN_DIR/vite.pid"
  if pid_alive "$pid_file"; then
    log "Vite は起動済みです (PID $(cat "$pid_file"))。"
    return
  fi
  if port_in_use "$FRONTEND_PORT"; then
    warn "port $FRONTEND_PORT は既に使用中です（別ターミナルの npm run dev 等）。そちらを使ってください。"
    return
  fi
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    log "npm install を実行します..."
    ( cd "$FRONTEND_DIR" && npm install ) >"$LOG_DIR/npm-install.log" 2>&1
  fi

  log "Vite を起動します (http://localhost:$FRONTEND_PORT)..."
  ( cd "$FRONTEND_DIR" && exec npm run dev -- --port "$FRONTEND_PORT" ) >"$LOG_DIR/vite.log" 2>&1 &
  echo $! > "$pid_file"
  disown
}

frontend_stop() {
  local pid_file="$RUN_DIR/vite.pid"
  if pid_alive "$pid_file"; then
    log "Vite を停止します..."
    pkill -P "$(cat "$pid_file")" 2>/dev/null || true
    kill "$(cat "$pid_file")" 2>/dev/null || true
  else
    log "Vite（このスクリプトが起動したもの）は動いていません。既存プロセスがあっても他ターミナルのものなので触りません。"
  fi
  rm -f "$pid_file"
}

# ---- サブコマンド ----

cmd_up() {
  pg_start
  backend_start
  frontend_start
  echo
  cmd_status
  echo
  log "フロント     : http://localhost:$FRONTEND_PORT"
  log "API ドキュメント: http://localhost:$BACKEND_PORT/api/docs/"
  log "管理サイト   : http://localhost:$BACKEND_PORT/admin/"
  log "停止するには: scripts/local-dev.sh down"
}

cmd_down() {
  frontend_stop
  backend_stop
  pg_stop
}

cmd_status() {
  pg_status
  if pid_alive "$RUN_DIR/django.pid"; then
    echo "Django     : 起動中 (PID $(cat "$RUN_DIR/django.pid"), port $BACKEND_PORT)"
  elif port_in_use "$BACKEND_PORT"; then
    echo "Django     : 起動中（このスクリプト管理外, port ${BACKEND_PORT}）"
  else
    echo "Django     : 停止"
  fi
  if pid_alive "$RUN_DIR/vite.pid"; then
    echo "Vite       : 起動中 (PID $(cat "$RUN_DIR/vite.pid"), port $FRONTEND_PORT)"
  elif port_in_use "$FRONTEND_PORT"; then
    echo "Vite       : 起動中（このスクリプト管理外, port ${FRONTEND_PORT}）"
  else
    echo "Vite       : 停止"
  fi
}

cmd_logs() {
  local target="${1:-django}"
  case "$target" in
    django) tail -f "$LOG_DIR/django.log" ;;
    vite) tail -f "$LOG_DIR/vite.log" ;;
    postgres) tail -f "$LOG_DIR/postgres.log" ;;
    *) err "不明なログ対象: ${target}（django / vite / postgres）"; exit 1 ;;
  esac
}

cmd_seed_demo() {
  backend_env_setup
  log "デモデータを投入します（社員・外注先・打刻履歴・休暇申請等）..."
  ( cd "$BACKEND_DIR" && source .venv/bin/activate && python3 manage.py create_demo_data )
}

case "${1:-}" in
  up) cmd_up ;;
  down) cmd_down ;;
  status) cmd_status ;;
  logs) cmd_logs "${2:-}" ;;
  seed-demo) cmd_seed_demo ;;
  *)
    cat <<EOF
使い方: scripts/local-dev.sh <command>

  up          PostgreSQL・Django・Vite をまとめて起動
  down        まとめて停止
  status      起動状況を表示
  logs [名前]  ログを追う（django / vite / postgres。省略時は django）
  seed-demo   デモデータ（社員・外注先・打刻履歴等）を投入
EOF
    exit 1
    ;;
esac
