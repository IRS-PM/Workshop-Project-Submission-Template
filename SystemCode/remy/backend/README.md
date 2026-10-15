# `remy` backend

Auth API for Remy: FastAPI on uvicorn, PostgreSQL via asyncpg, Argon2id password
hashing, and a Bloom filter in front of the username existence check.

## Run it

This is a uv workspace member, so there are two ways in. Either works; the
`.venv` here is self-contained and does not need uv at all once created.

**With uv, from `SystemCode/`:**

```bash
uv sync --package remy-backend
uv run --package remy-backend uvicorn main:app --reload --port 8000
```

**With the backend's own venv, from this directory:**

```bash
uv venv --python 3.12          # or: python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -e .
.venv/bin/pip install -r requirements-dev.txt   # tests only
.venv/bin/python -m uvicorn main:app --reload --port 8000
```

`requirements.txt` is the frozen runtime set and `requirements-dev.txt` adds the
test tools. Both are pinned exactly; regenerate with `uv pip freeze` after
changing `pyproject.toml`, which stays the source of truth for version ranges.

## Database

```bash
createdb remy_main                 # if it does not exist yet
psql -d remy_main -f db.sql

export REMY_DATABASE_URL="postgresql://localhost:5432/remy_main"
export REMY_JWT_SECRET="$(openssl rand -base64 48)"
```

Interactive docs at http://127.0.0.1:8000/docs. See `.env.example` for settings.

## Endpoints

| Method | Path                       | Purpose |
| ------ | -------------------------- | ------- |
| `POST` | `/auth/signup`             | Create an account. `201`, or `409` if taken. |
| `POST` | `/auth/signin`             | Check credentials. `200`, or `401`. |
| `POST` | `/auth/available`          | Is this username free? Answered from memory where possible. |
| `GET`  | `/health`                  | Liveness, plus live Bloom filter stats. |

Usernames are lowercased before validation, so `Alice` and `alice` are the same
account. The accepted shape matches the `app_user_username_format` constraint in
`db.sql`, so a bad username fails at the edge with a readable message rather
than as a constraint violation.

## Passwords

Stored as Argon2id PHC strings (`$argon2id$v=19$m=65536,t=3,p=4$salt$hash`). The
salt and cost parameters live inside that string, which is why `app_user` has no
salt column. `signin` transparently re-hashes when the stored parameters fall
behind the current ones.

`signin` verifies against a throwaway hash when the username does not exist, so
a missing account costs the same wall clock time as a wrong password. Measured
over 8 requests each: wrong password 41ms, unknown username 36ms, correct
password 36ms. Without that step the unknown-username path returns in about a
millisecond and becomes a username enumeration oracle.

## The Bloom filter

Built at startup from `SELECT username FROM app_user`, held in process memory,
rebuilt on restart. Each worker keeps its own copy, so there is nothing to
invalidate or keep in sync.

Its error is one-sided, and the whole design leans on that:

* **Miss** - certainly not registered. `signup` skips the existence query and
  goes straight to the insert. This is the common case.
* **Hit** - probably registered, roughly 1% of hits are wrong at full capacity.
  `signup` confirms against the table before rejecting, so a false positive
  costs one query rather than a wrongly refused username.

The filter is an optimisation, never the authority. Two concurrent requests can
both pass the check and race to insert; the primary key on `app_user.username`
is what actually settles it, and `signup` catches the unique violation and
returns `409`.

There is no `remove()`, because entries share bits. Deleting an account leaves a
permanent false positive until the process restarts and rebuilds the filter.
That costs one wasted query on the next sign up attempt for that name, and
nothing else.

`signin` deliberately does *not* consult the filter: answering "certainly not
registered" without touching the database would be visibly faster than a wrong
password, which is the enumeration leak the dummy verification above exists to
prevent.

Sizing comes from `REMY_BLOOM_CAPACITY` and `REMY_BLOOM_ERROR_RATE` using the
standard formulas (`m = -n ln p / (ln 2)²`, `k = (m/n) ln 2`). At the defaults,
100k accounts at 1%, that is a 959,000-bit filter with 7 hash functions -
about 120 KB. Capacity is what you expect to hold, not what you hold today: the
false positive rate degrades past it.

## Tests

```bash
uv run --package remy-backend pytest remy/backend/tests   # from SystemCode/
.venv/bin/python -m pytest tests                          # from here
```

Covers the property sign up depends on (no false negatives), that the measured
false positive rate matches the sizing maths, and that bad sizing is rejected.
