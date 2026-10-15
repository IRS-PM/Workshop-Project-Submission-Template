# `remy`: Meal weekly planner recommendation app for the lazy ones

This is the dev documents for the application

## Run everything locally

```bash
./start-all.sh            # auth backend :8010, Remy API :8081, frontend :3000
./start-all.sh --no-open  # same, without opening the browser
```

The script runs the whole app in Docker Compose (`../docker-compose.yml`):
PostgreSQL, the auth backend, the Remy API and the Next.js frontend. It builds
the images, waits until every service is healthy, opens the frontend, then
streams live logs from all of them, prefixed with the service name. Ctrl+C
stops and removes the containers. PostgreSQL data stays in the
`remy_postgres_data` volume between runs; `db.sql` creates the schema the first
time. Ports can be changed with `BACKEND_PORT`, `API_PORT` and `FRONTEND_PORT`,
for example `BACKEND_PORT=8000 ./start-all.sh`.

You need Docker with Compose v2 running, and a settings file `SystemCode/.env.nonprod`
(copy `SystemCode/.env.example` and fill it in; see [docs/docker_compose.md](../docs/docker_compose.md)).
It holds the Neo4j connection, `REMY_JWT_SECRET` (without it, sign-ins end whenever
the backend restarts), and the database and Langfuse keys. The local Neo4j container
is not started unless you ask for it.

Code changes need a restart of the script, which rebuilds the changed images.
For hot reload, run a service on its own instead (see its README).

If a port is held by something other than Docker, such as an older run of the
servers outside Docker, the script names the process and exits without
starting anything. It also refuses to start a second copy while Remy is already
running in Docker.
