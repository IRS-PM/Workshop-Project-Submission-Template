# Remy API + local Langfuse

## Docker: one command

From `SystemCode/`, with the settings in `.env.nonprod` (see
[docs/docker_compose.md](../docs/docker_compose.md) for the file):

```sh
docker compose --env-file .env.nonprod up -d --build --wait
```

This starts the frontend, auth backend, Remy API, and the Langfuse stack
(web, worker, gateway, PostgreSQL, ClickHouse, Redis, and the S3-compatible store
SeaweedFS). Add `--profile neo4j` to also run a local Neo4j. The API uses the
`NEO4J_*` values from the same file.

- **Application: `http://localhost:3100`**
- API: `http://localhost:8000/docs`
- Langfuse dashboard: `http://localhost:<LANGFUSE_PORT>` (default 3031)

The Langfuse admin login is `LANGFUSE_INIT_USER_EMAIL` and
`LANGFUSE_INIT_USER_PASSWORD` in the settings file. The API gets its Langfuse keys
and `REMY_EVALUATION_TOKEN` from the same file. Keep the settings file private
(git-ignored, mode 0600). The Langfuse dashboard and gateway are bound to localhost
only; never expose them publicly.

Named volumes keep Langfuse data and the local evaluation snapshots.
`docker compose --env-file .env.nonprod down -v` **deletes that data**.

Other commands:

```sh
docker compose --env-file .env.nonprod down        # stop; keep volumes
docker compose --env-file .env.nonprod logs -f api
```

## Workflow and the three metrics (slides 18–19)

1. `POST /api/v1/plan` creates a `meal-plan` trace with nested retrieval, filtering,
   ranking, solving, and response spans. Record durations, sanitized failure types,
   candidate counts, empty retrievals, plan status, and relaxation count.
2. Save the successful ranking snapshot in SQLite. The response includes
   `trace_id` and `evaluation_id`; these are nullable outside Docker when disabled
   or unavailable. All tracing/storage failures leave meal planning available.
3. A protected endpoint presents the original request and shuffled candidates,
   without ranking scores/order, plan order, trace link, or previous judgments.
4. A reviewer grades every candidate **0–3**. Persist the grades and computed
   metrics before queueing scores on the original Langfuse trace.

**Metrics evaluate `rank_candidates` before the solver, not the final meal-slot
order.** The evaluation pool is its bounded output (up to 300 recipes), not every
recipe in Neo4j. Compare ranking methods on the same pool/grading protocol; these
metrics do not measure retrieval recall. Candidate nutrients are per-recipe values
before scaling by requested servings.

| Langfuse score | Definition |
| --- | --- |
| `nDCG@3` | Top-three DCG uses `(2^grade - 1) / log2(rank + 1)`, divided by ideal top-three DCG from the **whole graded pool**. All-zero ideal returns 0. |
| `Precision@3` | Number of top-three recipes graded **≥2**, divided by **3**. Missing positions in shorter lists count as not relevant. |
| `pairwise_accuracy` | Fraction of unequal-grade pairs in the whole ranking with the better recipe first. Exclude ties. No comparable pairs returns `null` locally and emits no Langfuse score. |

Set `REMY_DATA_VERSION` and `LANGFUSE_RELEASE` in the selected API env file to label
data/code versions. Root `meal-plan` durations support p50/p95 **planner** latency;
do not mix nested stages into percentiles. HTTP validation/serialization and network
round-trip time are outside that measurement.

## Collect actual human judgments

Create a plan, then copy its `evaluation_id`:

```sh
curl -fS http://localhost:8000/api/v1/plan \
  -H 'Content-Type: application/json' \
  -d '{"horizon_days":1,"meals_per_day":3}'

# Copy REMY_EVALUATION_TOKEN from private .env.nonprod; do not put it in a browser app.
export REVIEWER_TOKEN='your-local-reviewer-token'
export EVALUATION_ID='evaluation_id-from-plan-response'
curl -fS "http://localhost:8000/api/v1/evaluations/$EVALUATION_ID" \
  -H "Authorization: Bearer $REVIEWER_TOKEN" > candidates.json
```

Use a consistent rubric: **0** unsuitable, **1** marginal, **2** relevant, **3** highly
relevant to the request. Grade blind, independently of the returned plan and Langfuse
ranking trace. Put one integer grade per returned ID in `human-grades.json`:

```json
{"grades":{"actual-recipe-id-1":3,"actual-recipe-id-2":2,"actual-recipe-id-3":0}}
```

Replace the example IDs and grade the **entire** recorded pool, not just three
recipes. Missing/unknown IDs, floats, booleans, grades outside 0–3, and duplicate
ranking IDs are rejected.

```sh
curl -fS "http://localhost:8000/api/v1/evaluations/$EVALUATION_ID/grades" \
  -H "Authorization: Bearer $REVIEWER_TOKEN" \
  -H 'Content-Type: application/json' --data-binary @human-grades.json
```

Response: `metrics`, `trace_id`, and `langfuse_scores_queued`. Human score metadata
contains `judge=human`, evaluation ID, and metric version `v1`. Grades are immutable;
repeat the same request to retry publication with stable score IDs. Changed grades
return 409. `queued=true` is SDK acceptance, not remote delivery confirmation; verify
in Langfuse and retry after an outage. No clicks/saves or LLM labels are passed off
as human judgments. A snapshot made without a trace cannot later publish to one.

## Verification

```sh
# Unit checks: no Docker, Neo4j, or real Langfuse credentials needed.
uv run --frozen --package remy-api python -m unittest discover \
  -s remy/api/tests -p test_monitoring.py
uv run --frozen --package remy-api python -m unittest discover \
  -s scripts -p test_init_langfuse.py
uv run --frozen --package remy-api python -m unittest discover \
  -s remy/api/tests -p test_langfuse_gateway.py
uv lock --check

# Live Docker check: verifies project auth, trace export, worker processing,
# and all three persisted metrics through the public Langfuse API.
uv run --frozen --package remy-api python scripts/check_langfuse.py
```

The live check creates a clearly labeled **synthetic fixture** trace in environment
`integration-test`; its scores are not human evaluations or production quality claims.
A real planner request was also verified: HTTP 200, all six observations present in
local Langfuse, and the protected blind-grading endpoint working. Its actual human
grades remain pending. Passwordless dashboard access was verified from a fresh HTTP
client without supplying credentials or cookies; foreign Host/Origin requests are blocked.

The merged frontend's real Chromium E2E passes: signup, saved preferences, logout/login,
streamed planning through the frontend proxy, all six Langfuse spans, and protected
candidate review. Evidence: `SystemCode/target/e2e/meal-plan.png` and `result.json`.
Frontend unit tests: **22 passed**; lint clean; production npm audit clean after the
Next.js 16.4.0 security patch. API/domain suite: **34 passed, 4 pre-existing conversion
failures**. The PR fixed the former oatmeal-alias failure. Architecture lint is blocked by the
existing `.importlinter` file's invalid `[[contracts]]` syntax. Those are unchanged.

## Privacy and limitations

Raw dietary/allergy requests, recipe instructions, and raw exception messages are
not sent to Langfuse. Export only structural settings/constraint counts, versions,
recipe/plan/evaluation IDs, counts/statuses, and aggregate scores. Actual constraints
and candidate details are stored in protected local SQLite for review; protect its
volume/backups and grading files, and apply retention. SQLite is intentionally
single-deployment; use shared PostgreSQL before scaling API replicas.

Ranking evaluation does not establish dietary safety. Existing allergen/dietary
checks now screen known conflicts per recipe in `filtering.py`. Restricted requests
run normally; unknown evidence remains eligible for best-effort suggestions and is
explicitly marked `unverified`, never `passed`. Both plan and chat UIs warn that these
results are not guaranteed allergy-safe or diet-compliant. No blanket 503 guard remains. No LLM/LangGraph rebuild, token-cost tracking,
automatic grading, click/save tracking, or grading UI is added.

For non-Docker API use, tracing still defaults off. Configure the optional Cloud or
self-hosted settings from `.env.example`, then run:

```sh
uv run --env-file .env.nonprod --package remy-api uvicorn api.main:app --reload
```
