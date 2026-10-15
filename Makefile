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

.PHONY: test-docker
test-docker: ## Тесты внутри Docker-образа backend (там есть Stockfish)
	$(COMPOSE) run --rm --build -e REQUIRE_STOCKFISH=1 api pytest
