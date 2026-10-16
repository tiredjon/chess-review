.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose
BACKEND := cd backend && uv run
WEB := cd web &&

.PHONY: help
help: ## Список команд
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# --- Docker ---

.PHONY: up
up: ## Поднять весь стек (postgres, redis, migrate, api, worker, web)
	$(COMPOSE) up -d --build --wait

.PHONY: down
down: ## Остановить стек
	$(COMPOSE) down

.PHONY: logs
logs: ## Логи всех сервисов
	$(COMPOSE) logs -f --tail=100

.PHONY: services
services: ## Поднять только postgres и redis (для локальной разработки и тестов)
	$(COMPOSE) up -d --wait postgres redis

# --- Backend ---

.PHONY: install
install: ## Установить зависимости backend и web
	cd backend && uv sync
	$(WEB) npm ci

.PHONY: migrate
migrate: ## Применить миграции к локальной БД
	$(BACKEND) alembic upgrade head

.PHONY: revision
revision: ## Новая миграция: make revision m="описание"
	$(BACKEND) alembic revision --autogenerate -m "$(m)"

.PHONY: fmt
fmt: ## Автоформатирование
	$(BACKEND) ruff format .
	$(BACKEND) ruff check --fix .

# --- Проверки (CI) ---

.PHONY: lint
lint: lint-backend lint-web ## Все линтеры и проверки типов

.PHONY: lint-backend
lint-backend:
	$(BACKEND) ruff format --check .
	$(BACKEND) ruff check .
	$(BACKEND) mypy

.PHONY: lint-web
lint-web:
	$(WEB) npm run lint
	$(WEB) npx next typegen >/dev/null
	$(WEB) npx tsc --noEmit

.PHONY: test
test: services lint ## CI: линтеры + все тесты backend (поднимает postgres/redis)
	$(BACKEND) pytest --cov --cov-report=term-missing:skip-covered

PSQL := $(COMPOSE) exec -T postgres psql -U chess -d chess_review -tAc
DEV_USER_ID ?= 00000000-0000-0000-0000-000000000001

.PHONY: e2e
e2e: ## Playwright smoke сквозь стек (нужен `make up`; E2E_BASE_URL, по умолчанию localhost:$$WEB_PORT)
	@# Первый зарегистрированный получает данные dev-пользователя — это не должен быть тест.
	@if [ "$$($(PSQL) "SELECT count(*) FROM users WHERE id = '$(DEV_USER_ID)' AND password_hash IS NULL" 2>/dev/null)" = "1" ]; then \
		echo "Сначала зарегистрируйтесь в приложении: иначе тестовый пользователь получит данные dev-пользователя."; exit 1; fi
	$(WEB) E2E_BASE_URL=$${E2E_BASE_URL:-http://localhost:$${WEB_PORT:-3000}} npx playwright test; \
		status=$$?; $(PSQL) "DELETE FROM users WHERE email LIKE 'e2e-%@example.com'" >/dev/null 2>&1; exit $$status

.PHONY: test-docker
test-docker: ## Тесты внутри Docker-образа backend (там есть Stockfish)
	$(COMPOSE) run --rm --build -e REQUIRE_STOCKFISH=1 api pytest
