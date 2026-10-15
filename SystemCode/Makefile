SHELL := /bin/sh

UV ?= uv
COMPOSE ?= docker compose --env-file .env.$(DBT_TARGET)
API_PACKAGE := remy-api
CRAWLER_PACKAGE := remy-data-crawler
DBT_PACKAGE := remy-data-preparation
DBT_TARGET ?= nonprod
export DBT_TARGET

-include .env.$(DBT_TARGET)
export NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD NEO4J_DATABASE NEO4J_HTTP NEO4J_USER NEO4J_BATCH_SIZE \
       AURA_INSTANCEID AURA_INSTANCENAME JEV_API_KEY JEV_MODEL RANKER_MODE

.PHONY: help eval-jev prepare-data up install sync lock check build build-all up-prod up-all down logs langfuse langfuse-init \
        api crawler dbt dbt-all serve-neo4j serve-neo4j-replace fulfillment frontend-install clean _neo4j-creds \
        _seeds-check _nonprod-only

help:
	@printf '%s\n' \
		'make prepare-data     Full data pipeline (nonprod): deps, seeds check, dbt, local Neo4j, graph, fulfillment' \
		'make up               Start the whole stack in Docker (nonprod adds local Neo4j) and wait until healthy' \
		'make eval-jev         Grade human-graded plans with the Jev judge and report agreement (needs JEV_API_KEY)' \
		'make fulfillment      Rebuild :BEST_FULFILLMENT edges in Neo4j (run after serve-neo4j)' \
		'make install          Install all Python workspace dependencies' \
		'make lock             Resolve and update uv.lock' \
		'make check            Verify uv.lock is current' \
		'make api              Run the API locally with reload' \
		'make crawler          Run the crawler module' \
		'make dbt              Build dbt models except the Neo4j serving model' \
		'make dbt-all          Build dbt models, then load them into Neo4j' \
		'make serve-neo4j      Load built marts into Neo4j' \
		'make serve-neo4j-replace  Replace the existing Neo4j recipe graph' \
		'make build            Build the API image' \
		'make build-all        Build API, jobs, and optional frontend images' \
		'make up               Start API, Neo4j, and local Langfuse' \
		'make up-prod          Start webapp, auth backend, API, and Langfuse with production Neo4j' \
		'make langfuse         Start the local Langfuse dashboard and worker' \
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
	cd remy/data-preparation && mkdir -p target/$(DBT_TARGET)/staging target/$(DBT_TARGET)/ducklake/data && \
		DBT_TARGET=$(DBT_TARGET) $(UV) run --package $(DBT_PACKAGE) dbt build --profiles-dir . --exclude tag:serving

_neo4j-creds:
	@test -n "$$NEO4J_PASSWORD" || { echo "Set NEO4J_PASSWORD or add it to .env.$(DBT_TARGET)"; exit 1; }

# Seeds that dbt reads (see remy/data-preparation/README.md). Missing ones fail the build.
SEEDS := remy/data-preparation/seeds
_seeds-check:
	@for f in 13k-recipe/13k-recipes.csv central_food/branded_food.csv central_food/food.csv \
	          central_food/food_component.csv central_food/food_nutrient/data.parquet \
	          fairprice/price_mapped_nutrients.csv fairprice/retail_search_listing.csv \
	          fairprice/retail_aisle_listing.csv; do \
	  test -f "$(SEEDS)/$$f" || { echo "Missing seed file: $(SEEDS)/$$f"; exit 1; }; \
	done

# prepare-data replaces the Neo4j graph, so it only runs against the local nonprod setup.
_nonprod-only:
	@test "$(DBT_TARGET)" = "nonprod" || { echo "prepare-data only runs with DBT_TARGET=nonprod (it replaces the graph)"; exit 1; }

# One command for the whole data pipeline. Rebuilds the nonprod DuckDB and DuckLake
# state from the seeds, so a previous partial run cannot leave broken files behind.
prepare-data: _nonprod-only _neo4j-creds install _seeds-check
	rm -rf remy/data-preparation/target/$(DBT_TARGET) remy/data-preparation/target/$(DBT_TARGET).duckdb
	$(MAKE) dbt DBT_TARGET=$(DBT_TARGET)
	$(COMPOSE) --profile neo4j up -d --wait neo4j
	$(MAKE) serve-neo4j DBT_TARGET=$(DBT_TARGET)
	$(MAKE) fulfillment DBT_TARGET=$(DBT_TARGET)
	@echo "Data ready: local Neo4j loaded and :BEST_FULFILLMENT rebuilt. Run 'make up' next."

# Runs inside the API container, where the evaluation database lives, then copies the report out.
eval-jev:
	@test -n "$$JEV_API_KEY" || { echo 'Set JEV_API_KEY in .env.$(DBT_TARGET) first'; exit 1; }
	$(COMPOSE) exec -T api /workspace/.venv/bin/python -m api.features.plan.judge_eval --out /workspace/target/eval/jev_report.json
	$(COMPOSE) cp api:/workspace/target/eval/jev_report.json target/eval/jev_report.json
	@echo 'Report: target/eval/jev_report.json'

fulfillment: _neo4j-creds
	$(UV) run --package $(API_PACKAGE) python remy/data-preparation/scripts/rebuild_best_fulfillment.py

dbt-all: _neo4j-creds
	$(MAKE) dbt DBT_TARGET=$(DBT_TARGET)
	$(MAKE) serve-neo4j DBT_TARGET=$(DBT_TARGET)

serve-neo4j: _neo4j-creds
	cd remy/data-preparation && DBT_TARGET=$(DBT_TARGET) NEO4J_REPLACE=true $(UV) run --package $(DBT_PACKAGE) dbt run --profiles-dir . --select recipe_graph_to_neo4j

serve-neo4j-replace: serve-neo4j

langfuse-init:
	$(UV) run --frozen --package $(API_PACKAGE) python scripts/init_langfuse.py

build build-all up-all down logs: langfuse-init

langfuse: langfuse-init
	$(COMPOSE) up -d --build --wait langfuse-gateway langfuse-worker

up-prod: DBT_TARGET=prod
up-prod: langfuse
	$(COMPOSE) up -d --build --wait frontend

build:
	$(COMPOSE) build api

build-all:
	$(COMPOSE) --profile neo4j --profile jobs build

# One command for the app. Nonprod also starts the local Neo4j the API uses.
NEO4J_PROFILE := $(if $(filter nonprod,$(DBT_TARGET)),--profile neo4j,)

up: langfuse-init
	$(COMPOSE) $(NEO4J_PROFILE) up -d --build --wait
	@echo ""
	@echo "Remy is up:"
	@echo "  Web app    http://localhost:$${FRONTEND_PORT:-3100}"
	@echo "  API docs   http://localhost:$${API_PORT:-8000}/docs"
	@echo "  Langfuse   http://localhost:$${LANGFUSE_PORT:-3031}"
	@echo "  Demo login demo / remy-demo-account"

up-all:
	$(COMPOSE) --profile neo4j --profile jobs up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

frontend-install:
	npm --prefix remy/frontend ci

clean:
	rm -rf .venv
