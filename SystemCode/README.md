# Remy

Smart weekly meal-planning monorepo.

## Project directory structure

```markdown
# Remy monorepo structure

remy/
├── README.md
├── pyproject.toml                          # workspace root (uv/poetry/hatch)
├── .importlinter                           # dependency-direction contracts
├── docs/
│   ├── API_rules.md
│   ├── neo4j_db_design.md
│   ├── system_design_v3.md
│   ├── tech_stack.md
│   └── adr/
│       └── 0001-domain-shared-kernel.md    # ADR for the domain/ package
│
├── domain/                                 # ★ Shared Kernel — pure logic, no I/O
│   ├── pyproject.toml
│   ├── src/
│   │   └── domain/
│   │       ├── __init__.py
│   │       ├── types.py                    # NutrientProfile, CheckState
│   │       ├── units.py                    # to_grams, unit tables
│   │       ├── nutrients.py                # scale/sum/per_serving, portion math
│   │       └── exceptions.py               # DomainError, UnitConversionError
│   └── tests/
│       ├── test_types.py
│       ├── test_units.py
│       └── test_nutrients.py
│
├── api/                                    # backend API (FastAPI)
│   ├── pyproject.toml
│   ├── src/
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── core/
│   │       │   ├── config.py
│   │       │   └── exceptions.py           # AppError, error envelope
│   │       └── features/
│   │           ├── calculator/
│   │           │   ├── __init__.py
│   │           │   ├── service.py
│   │           │   ├── conversion.py       # shim → domain.units (deprecated)
│   │           │   └── nutrition.py        # shim → domain.nutrients (deprecated)
│   │           └── plan/                   # ★ new feature
│   │               ├── __init__.py
│   │               ├── router.py
│   │               ├── dependencies.py
│   │               ├── schemas.py
│   │               ├── models.py
│   │               ├── repository.py       # batched Cypher
│   │               ├── filtering.py        # orchestrates workflows.rules.*
│   │               ├── ranking.py          # score(r), pool cap K
│   │               ├── solver.py           # CP-SAT model + relaxations
│   │               ├── aggregation.py      # day/horizon rollups
│   │               ├── service.py          # orchestration
│   │               └── exceptions.py
│   └── tests/
│       ├── conftest.py
│       └── features/
│           ├── calculator/
│           │   └── test_service.py
│           └── plan/
│               ├── fixtures/
│               │   ├── recipes.py
│               │   └── neo4j_rows.py
│               ├── test_schemas.py
│               ├── test_repository.py
│               ├── test_filtering.py
│               ├── test_ranking.py
│               ├── test_solver.py
│               ├── test_aggregation.py
│               ├── test_router.py
│               ├── test_golden.py
│               └── test_determinism.py
│
├── app/                                    # frontend
│   ├── package.json
│   └── src/
│       └── ...
│
├── data-crawler/                           # data collection job
│   ├── pyproject.toml
│   └── src/
│       └── crawler/
│           └── ...
│
├── data-preparation/                       # dbt + Neo4j loader
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── staging/
│   │   ├── intermediate/
│   │   └── marts/
│   │       └── mart_allergen_screening_contract.sql
│   ├── loaders/
│   │   └── neo4j_loader.py
│   └── tests/
│       └── contracts/
│           └── test_allergen_screening_contract.py
│
└── workflows/                              # rule checks used by the plan filter
    ├── pyproject.toml
    ├── src/
    │   └── workflows/
    │       ├── __init__.py
    │       ├── state.py                    # re-exports CheckState from domain.types
    │       └── rules/
    │           ├── __init__.py
    │           ├── allergen.py             # check_allergen*, resolve_allergen_key
    │           ├── dietary.py              # check_halal_compliance, check_vegetarian_compliance
    │           ├── nutrition.py            # check_carbs_compliance ONLY (rule, not math)
    │           └── data/
    │               ├── allergen_aliases.json
    │               └── animal_derived.json
    └── tests/
        ├── rules/
        │   ├── test_allergen.py
        │   ├── test_dietary.py
        │   └── test_nutrition_rules.py
        └── fixtures/
```

---

## Package roles

| Package             | Role                                                      | Depends on             |
|---------------------|-----------------------------------------------------------|------------------------|
| `domain`            | Shared Kernel: pure arithmetic + shared vocabulary        | (nothing)              |
| `workflows`         | Rule checks (allergen, dietary, nutrition, budget) that return `CheckState` | `domain`               |
| `api`               | FastAPI delivery layer; HTTP, orchestration, solver       | `domain`, `workflows`  |
| `app`               | Frontend                                                  | `api` (over HTTP)      |
| `data-crawler`      | Scheduled data collection                                 | `domain` (if needed)   |
| `data-preparation`  | dbt transforms + Neo4j loader                             | `domain` (if needed)   |

---

## Dependency direction (enforced)

```
app ──HTTP──▶ api ──▶ workflows ──▶ domain
                │                       ▲
                └───────────────────────┘

domain      ✗ must NOT import api/, workflows/, app/
workflows   ✗ must NOT import api/, app/
api         ✗ must NOT import app/
```

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose
- Git LFS for the dbt seed data

## Setup

Run from `SystemCode`:

```bash
git lfs pull
make install
```

Environment files are local and not committed:

- `.env.nonprod` — local Docker development
- `.env.prod` — production services

Neo4j requires `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`.

## Run the app with Docker

```bash
./remy/start-all.sh
```

Starts PostgreSQL, the auth backend, the Remy API and the frontend with Docker
Compose. See [docs/docker_compose.md](docs/docker_compose.md) for setup,
checks and troubleshooting.

## Common commands

```bash
make help          # list commands
make up            # start the API and local Neo4j
make down          # stop containers
make dbt           # build and test dbt models
make dbt-all       # build dbt models and load Neo4j
make api           # run the API locally
make crawler       # run the crawler
```

Use production configuration explicitly:

```bash
make dbt-all DBT_TARGET=prod
```

See `remy/data-preparation/README.md` for dbt and Neo4j details.
