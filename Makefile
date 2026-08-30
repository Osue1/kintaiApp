.DEFAULT_GOAL := help
COMPOSE := docker compose

help: ## コマンド一覧
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## DBとバックエンドを起動
	$(COMPOSE) up -d --build

down: ## 停止
	$(COMPOSE) down

logs: ## ログを追う
	$(COMPOSE) logs -f backend

migrate: ## マイグレーションを作成して適用
	$(COMPOSE) exec backend python manage.py makemigrations
	$(COMPOSE) exec backend python manage.py migrate

seed: ## 初期データを投入
	$(COMPOSE) exec backend python manage.py seed_initial_data

superuser: ## 管理者を作成
	$(COMPOSE) exec backend python manage.py createsuperuser

test: ## バックエンドのテスト
	$(COMPOSE) exec backend pytest

lint: ## Lint
	$(COMPOSE) exec backend ruff check .
	cd frontend && npm run lint

schema: ## OpenAPI から TypeScript の型を生成
	cd frontend && npm run gen:api

front: ## フロントの開発サーバー
	cd frontend && npm run dev

.PHONY: help up down logs migrate seed superuser test lint schema front
