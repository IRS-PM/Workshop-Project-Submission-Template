# Complete, production-ready FastAPI layered architecture project structure

```
remy/
│
├── .env                          # Local env vars (git-ignored)
├── .env.example                  # Template of required env vars
├── .gitignore
├── pyproject.toml                # Deps + ruff, mypy, pytest, import-linter
├── setup.cfg                     # import-linter contracts
├── README.md
├── Dockerfile
├── docker-compose.yml            # api + worker + postgres + redis
├── alembic.ini
│
├── alembic/
│   ├── env.py                    # Imports app.models_registry
│   └── versions/
│
├── src/
│   └── app/
│       │
│       ├── __init__.py
│       ├── main.py               # App factory, lifespan, ONE AppError handler
│       ├── worker.py             # Worker entrypoint (ARQ) — imports feature tasks
│       ├── config.py             # Pydantic Settings (single source of truth)
│       ├── dependencies.py       # Cross-cutting ONLY: pagination, request-id
│       ├── models_registry.py    # Imports every models.py for Alembic autogen
│       │
│       ├── core/                 # Side-effectful infrastructure. No feature imports.
│       │   ├── __init__.py
│       │   ├── database.py       # Engine, sessionmaker, Base, get_db (SOLE home)
│       │   ├── security.py       # Hashing, JWT primitives (if auth lands)
│       │   ├── exceptions.py     # AppError base WITH status_code
│       │   ├── logging.py        # Structured JSON logging
│       │   ├── pagination.py     # Reusable pagination params
│       │   ├── queue.py          # ARQ pool + enqueue() helper
│       │   ├── cache.py          # Redis cache helpers
│       │   └── llm.py            # LLM client (if chat uses a provider directly)
│       │
│       ├── shared/               # Pure helpers, no I/O, no feature imports
│       │   ├── __init__.py
│       │   ├── types.py          # Paginated[T], error envelope, Annotated aliases
│       │   ├── units.py          # g ↔ kg, ml ↔ L, SGD formatting
│       │   └── utils.py
│       │
│       └── features/
│           │
│           ├── recipes/          # CATALOG — foundational, imported by others
│           │   ├── __init__.py   # PUBLIC API: RecipeService, RecipeRepository,
│           │   │                 # RecipeSummary, IngredientRef (DTOs only)
│           │   ├── router.py     # GET /recipes/{id}, GET /recipes (search)
│           │   ├── schemas.py    # RecipeResponse, RecipeSummary, IngredientOut
│           │   ├── service.py    # Retrieval, fulfillment mapping
│           │   ├── repository.py # Non-trivial queries only (joins, filters)
│           │   ├── models.py     # Recipe, Ingredient, RecipeIngredient
│           │   ├── dependencies.py
│           │   └── exceptions.py # RecipeNotFoundError: 404
│           │
│           ├── calculator/       # PURE MATH — no DB, no router state
│           │   ├── __init__.py   # PUBLIC API: CostNutritionCalculator
│           │   ├── router.py     # POST /calculate/cost-and-nutrition
│           │   ├── schemas.py    # Request: ingredient list. Response: consumed
│           │   │                 # vs. retail cost, macro/micro breakdown
│           │   ├── service.py    # Orchestrates repo lookups + pure math
│           │   ├── repository.py # FDC profile + retail SKU lookups
│           │   ├── models.py     # NutrientProfile, RetailSKU (or views)
│           │   ├── dependencies.py
│           │   ├── exceptions.py # UnknownIngredientError: 422
│           │   └── domain/       # PURE functions, no imports from app.*
│           │       ├── __init__.py
│           │       ├── cost.py   # Consumed vs. retail, package conversion
│           │       └── nutrition.py # Macro/micro aggregation
│           │
│           ├── dietary/          # RULE VERIFICATION — depends on recipes
│           │   ├── __init__.py   # PUBLIC API: DietaryVerifier
│           │   ├── router.py     # POST /verify-dietary
│           │   ├── schemas.py    # Recipe ID, constraints (halal, vegetarian…)
│           │   ├── service.py    # Evaluates compliance modes, flags conflicts
│           │   ├── dependencies.py
│           │   ├── exceptions.py # DietaryConflictError: 409
│           │   └── domain/       # PURE rules per diet type
│           │       ├── __init__.py
│           │       ├── rules.py  # halal, vegetarian, vegan, allergies
│           │       └── conflicts.py
│           │
│           ├── plans/            # GENERATION — depends on recipes,
│           │   │                 # calculator, dietary, recommendations
│           │   ├── __init__.py   # PUBLIC API: PlanService
│           │   ├── router.py     # POST /plan (202), GET /plan/{id}
│           │   ├── schemas.py    # PlanRequest, PlanStatus, PlanResponse
│           │   ├── service.py    # validate → enqueue → return. Commits.
│           │   ├── repository.py # Plan persistence, status queries
│           │   ├── models.py     # Plan, PlanRun
│           │   ├── dependencies.py
│           │   ├── exceptions.py # PlanNotReadyError: 409
│           │   ├── tasks.py      # THIN ARQ handler: calls domain.solver,
│           │   │                 # persists via repo, updates status.
│           │   └── domain/       # PURE solver — no DB, no I/O
│           │       ├── __init__.py
│           │       ├── solver.py # Constraints → days + violations
│           │       └── constraints.py
│           │
│           ├── recommendations/  # COLD-START — depends on recipes,
│           │   │                 # dietary, calculator
│           │   ├── __init__.py   # PUBLIC API: RecommendationService
│           │   ├── router.py     # POST /recommendations/cold-start
│           │   ├── schemas.py    # dietary_preference, target_daily_budget_sgd
│           │   ├── service.py    # Baseline algorithms
│           │   ├── dependencies.py
│           │   ├── exceptions.py
│           │   └── domain/       # PURE scoring/ranking
│           │       ├── __init__.py
│           │       └── ranker.py
│           │
│           └── chat/             # CONVERSATIONAL — depends on plans,
│               │                 # recipes, dietary via public APIs only
│               ├── __init__.py   # PUBLIC API: ChatService
│               ├── router.py     # POST /chat (SSE)
│               ├── schemas.py    # Session UUID, message, user_context
│               ├── service.py    # LangGraph workflow invocation + SSE gen
│               ├── repository.py # Chat history persistence
│               ├── models.py     # ChatSession, ChatMessage
│               ├── dependencies.py
│               ├── exceptions.py
│               └── graph/        # LangGraph nodes/edges (NOT domain/ —
│                   ├── __init__.py  #  this is I/O-orchestration, not
│                   ├── workflow.py  #  pure business logic)
│                   └── nodes.py
│
└── tests/
    ├── conftest.py               # Async client, test DB, ARQ test pool
    ├── e2e/
    │   └── test_smoke.py         # Real app + Postgres + Redis via compose
    ├── features/
    │   ├── recipes/
    │   ├── calculator/
    │   │   └── test_domain_cost.py   # Pure, no fixtures
    │   ├── dietary/
    │   │   └── test_domain_rules.py  # Pure
    │   ├── plans/
    │   │   ├── test_domain_solver.py # Pure
    │   │   └── test_tasks.py         # ARQ handler with test DB
    │   ├── recommendations/
    │   ├── chat/
    │   │   └── test_graph.py         # LangGraph nodes in isolation
    └── core/
```

## 🔑 Key Files Explained

- main.py — The composition root. It creates the FastAPI instance via create_app (), mounts all
  feature routers with prefixes like /api/v1/users, registers global exception handlers, and
  configures the lifespan context manager for startup/shutdown (DB pool, Redis connection).
- config.py — A single source of truth for configuration using pydantic-settings. Provides a
  settings object that's imported everywhere, with typed fields and validation for environment
  variables.
- core/database.py — Contains the async engine, async_session_maker, the declarative Base, and
  the get_db () dependency that yields a session per request and handles commit/rollback.
- Feature dependencies.py — Where the DI chain lives for that feature. This is the glue that
  wires get_db → Repository → Service, so routers only need to depend on the service.
- shared/types.py — For reusable generic types used across features, like Paginated[T] or custom
  Annotated types for common parameters.

## 📐 The Rules That Make This Structure Work

- Dependency direction is strictly inward: router → service → repository → models. A service
  never imports from router.py; a repository never imports from service.py.
- Features don't import from each other directly. If orders needs user data, it depends on an
  interface, an event, or a shared service — not features.users.repository.
- models.py never leaves the repository layer. Routers and services work with Pydantic schemas or
  domain objects, not SQLAlchemy models.
- Schemas are per-operation, not per-entity. Define UserCreate, UserUpdate, UserResponse rather
  than one User schema used everywhere.
- core/ and shared/ contain no business logic — only infrastructure and utilities.
