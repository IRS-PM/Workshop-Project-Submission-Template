SHELL := /bin/sh

UV ?= uv
COMPOSE ?= docker compose
API_PACKAGE := remy-api
CRAWLER_PACKAGE := remy-data-crawler
DBT_PACKAGE := remy-data-preparation

.PHONY: help install sync lock check build build-all up up-all down logs \
        api crawler dbt frontend-install clean

help:
	@printf '%s\n' \
		'make install          Install all Python workspace dependencies' \
		'make lock             Resolve and update uv.lock' \
		'make check            Verify uv.lock is current' \
		'make api              Run the API locally with reload' \
		'make crawler          Run the crawler module' \
		'make dbt              Run dbt build' \
		'make build            Build the API image' \
		'make build-all        Build API, jobs, and optional frontend images' \
		'make up               Start API and Neo4j' \
		'make up-all           Start all Compose profiles' \
		'make down             Stop Compose services' \
		'make logs             Follow Compose logs'

install: sync

sync:
	$(UV) sync --all-packages

lock:
	$(UV) lock

check:
	$(UV) lock --check

api:
	$(UV) run --package $(API_PACKAGE) uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

crawler:
	$(UV) run --package $(CRAWLER_PACKAGE) python -m data_crawler

dbt:
	$(UV) run --package $(DBT_PACKAGE) dbt build --project-dir remy/data-preparation

build:
	$(COMPOSE) build api

build-all:
	$(COMPOSE) --profile frontend --profile jobs build

up:
	$(COMPOSE) up --build api neo4j

up-all:
	$(COMPOSE) --profile frontend --profile jobs up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

frontend-install:
	@test -f remy/app/package.json || { echo 'remy/app/package.json is not initialized yet'; exit 1; }
	npm --prefix remy/app install

clean:
	rm -rf .venv
