# Running Remy with Docker Compose

This guide starts Remy in Docker: the database, the auth backend, the Remy API,
the web frontend, and the local Langfuse tracing stack. All commands run from
`SystemCode/`.

## One settings file

Every setting lives in one file per target:

| File           | Use                                                        |
|----------------|------------------------------------------------------------|
| `.env.nonprod` | Local development (the default)                            |
| `.env.prod`    | Production (Aura Neo4j); the same keys as nonprod          |

Both are git-ignored. `SystemCode/.env.example` lists every key. Copy it to the
file you need and fill it in, or let `scripts/init_langfuse.py` generate the
secrets:

```bash
cp .env.example .env.nonprod
uv run --package remy-api python scripts/init_langfuse.py --path .env.nonprod
```

The script only fills keys that are empty and never overwrites a value you set.

Compose needs the file passed explicitly, so every command below starts with
`docker compose --env-file .env.nonprod` (use `.env.prod` for production). The
scripts in this guide already do that.

For local development, `.env.nonprod` needs:

```dotenv
# Neo4j: the local container (make up / docker compose --profile neo4j)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<choose one>
NEO4J_DATABASE=neo4j
# The API container reaches the host's Neo4j through this
NEO4J_DOCKER_URI=bolt://host.docker.internal:7687

# Sign-in and database
REMY_JWT_SECRET=<openssl rand -base64 48>
REMY_POSTGRES_PASSWORD=<openssl rand -hex 24>
POSTGRES_PASSWORD=<same value as REMY_POSTGRES_PASSWORD>

# Langfuse and evaluation (filled by init_langfuse.py)
LANGFUSE_PORT=3031
REMY_EVALUATION_TOKEN=...
```

Without `REMY_JWT_SECRET` the backend invents a new secret on every start, so
everyone is signed out whenever it restarts.

Production uses Aura. Its `.env.prod` has the Aura `NEO4J_*` values and no
`NEO4J_DOCKER_URI`; the API then uses `NEO4J_URI` directly.

## What runs

| Service          | What it is                          | Open on your machine             |
|------------------|-------------------------------------|----------------------------------|
| `frontend`       | Next.js web app                     | http://localhost:3100            |
| `backend`        | Auth backend (FastAPI)              | http://localhost:8010/docs       |
| `api`            | Remy API: plans and calculator      | http://localhost:8000/docs       |
| `langfuse-web`   | Langfuse dashboard (via gateway)    | http://localhost:3031            |
| `postgres`       | PostgreSQL 17, user accounts        | not exposed                      |
| `langfuse-*`     | Langfuse storage: Postgres, ClickHouse, Redis, S3-compatible store (SeaweedFS) | not exposed |
| `neo4j`          | Local Neo4j (profile `neo4j` only)  | http://localhost:7474            |

`api` waits for the Langfuse services, so starting the API starts all of them.
`neo4j` is off by default: the API uses whatever `NEO4J_URI` points at.

## Before you start

1. Docker Desktop (or Docker Engine with Compose v2) is running:
   `docker compose version` works.
2. `.env.nonprod` exists and has the keys above.
3. The ports 8010, 8000, 3100 and 3031 are free. Otherwise see
   [Change the ports](#change-the-ports).

## Start it: two commands

```bash
make prepare-data   # once, or after the seed data changes: builds the graph
make up             # starts the whole stack in Docker and waits until healthy
```

`make prepare-data` installs the Python dependencies, checks that the seed files
are present, rebuilds the dbt models (PASS=104), starts the local Neo4j
container, loads the recipe graph into it, and rebuilds the `:BEST_FULFILLMENT`
edges the planner needs. It only runs for `nonprod`, because it replaces the
graph. It deletes the generated `remy/data-preparation/target/nonprod*` files
and rebuilds them from the seeds.

`make up` creates the Langfuse keys if they are missing, starts every service
(for `nonprod` also the local Neo4j), and prints the URLs when they are healthy.
Use `DBT_TARGET=prod make up` for production (Aura, no local Neo4j).

Both commands read `.env.nonprod`. The raw Compose commands are still there if
you need them: `docker compose --env-file .env.nonprod up -d --wait`.

The script alternative, `./remy/start-all.sh`, does the same start with a browser
pop-up and a live log stream (Ctrl+C stops and removes the containers).

## Check that it works

Open http://localhost:3100, sign in with the demo account (`demo` /
`remy-demo-account`, or **Try the demo**), and build a plan.

Or run the project's end-to-end test (signup, preferences, a streamed plan, and
the six Langfuse trace stages):

```bash
cd remy/frontend
E2E_API_URL=http://localhost:8000 E2E_FRONTEND_URL=http://localhost:3100 npm run test:e2e
```

From the terminal:

```bash
curl http://localhost:8010/health    # auth backend
curl http://localhost:8000/health    # Remy API
```

## Everyday commands

| Task                              | Command                                                              |
|-----------------------------------|----------------------------------------------------------------------|
| Status                            | `docker compose --env-file .env.nonprod ps`                          |
| Logs (all / one service)          | `docker compose --env-file .env.nonprod logs -f` / `... logs -f api` |
| Restart one service               | `docker compose --env-file .env.nonprod restart api`                 |
| Rebuild one service after changes | `docker compose --env-file .env.nonprod up -d --build api`           |
| Stop, keep data                   | `docker compose --env-file .env.nonprod down`                        |
| Stop and delete all data          | `docker compose --env-file .env.nonprod down -v`                     |

Containers run the code from their images, so there is no hot reload. After a
change, rebuild the service with `up -d --build <service>`.

## Change the ports

```bash
BACKEND_PORT=18010 API_PORT=18000 FRONTEND_PORT=13100 ./remy/start-all.sh
```

The same variables work in front of `docker compose up`. Keep `--build` when
you change `BACKEND_PORT`, because the frontend image has the backend's address
built in.

## The database

Accounts and preferences live in the `remy_postgres_data` volume and survive
`down`. `remy/backend/db.sql` only runs when the volume is empty, so schema edits
need `down -v` (this deletes all accounts).

## Troubleshooting

**`postgres` exits with "superuser password is not specified".** Set
`REMY_POSTGRES_PASSWORD` in `.env.nonprod`.

**`backend` is unhealthy with "password authentication failed".**
`POSTGRES_PASSWORD` no longer matches the password the volume was created
with. Put the old value back, or delete the volume with `down -v`.

**`api` is unhealthy, or plans and the calculator fail.** Check the
`NEO4J_*` values and `NEO4J_DOCKER_URI`, then `docker compose ... logs api`.
If plans say "No recipes with complete nutrition data", the
`rebuild_best_fulfillment.py` step has not been run (see above).

**Langfuse containers fail to pull.** The MinIO image is no longer pulled; the
S3 service is SeaweedFS, which needs no login.

**Everyone is signed out after a restart.** Set `REMY_JWT_SECRET` in
`.env.nonprod`.

**"port is already allocated".** Something else uses the port. Stop it, or
[change the ports](#change-the-ports).

## Durable plan runs

A meal plan runs as a LangGraph graph (`remy/api/src/api/features/plan/graph.py`):
retrieve, filter, rank, solve, generate. Each node's output is saved to Postgres
(schema `langgraph`, in `remy_main`) as soon as the node finishes.

- Each request gets a run id. The stream's first event is `run` with that id.
- To resume a run after a crash or restart, send the same `run_id` in the request
  body again. Completed nodes are not repeated; a finished run returns its stored
  plan.
- `REMY_CHECKPOINT_DB_URL` is required. The API refuses to start without it, so
  checkpointing cannot be silently skipped. Compose sets it from
  `REMY_POSTGRES_PASSWORD`.

Checked against the running stack: a run crashed inside `solve` in one process and
was resumed in a second process, which made no Neo4j fetch and returned the plan.

## Reranker mode and the Jev eval

- `RANKER_MODE=rule` (default): the nutrient ranking.
- `RANKER_MODE=jev`: Jev reranks the top 2K by probability that each recipe is a good fit,
  and keeps the top K. This needs `JEV_API_KEY` in the settings file. Without it the API
  refuses to start. A failed Jev call fails the plan; it does not fall back to the rule ranking.
- The snapshot records which ranker ran (`ranking_version`).

Eval task: grade the human-graded plans with the Jev judge and report agreement:

```bash
make eval-jev   # needs JEV_API_KEY; writes target/eval/jev_report.json
```

It reports agreement with the human grades (exact, within-one, quadratic kappa,
Spearman, relevance precision and recall), and nDCG@3, Precision@3 and pairwise
accuracy for the judge's ordering and the rule ordering. It needs at least 30
human-graded plans (`--min-evaluations`). Judge results are cached, so reruns are cheap.
