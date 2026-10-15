#!/usr/bin/env bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && /bin/pwd -P)"
SYSTEM_ROOT="$(dirname "$ROOT")"
BACKEND_PORT="${BACKEND_PORT:-8010}"
API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3100}"
OPEN_BROWSER=1

usage() {
  cat <<EOF
Usage: ./start-all.sh [--no-open]

Builds and starts Remy with Docker Compose: PostgreSQL, the auth backend, the
Remy API and the Next.js frontend. Opens the frontend in your browser once
everything answers. Press Ctrl+C to stop and remove the containers; the
PostgreSQL data is kept in a Docker volume for the next run.

Reads every setting from .env.nonprod (or .env.prod when DBT_TARGET=prod) in
SystemCode/. It needs REMY_POSTGRES_PASSWORD there. Compose sets the database
URL and CORS origins.

Ports can be changed with environment variables:
  BACKEND_PORT   auth backend   (default 8010)
  API_PORT       Remy API       (default 8000)
  FRONTEND_PORT  frontend       (default 3100)

A port that is already in use is replaced by the next free one.

Example: BACKEND_PORT=8000 ./start-all.sh --no-open
EOF
}

for arg in "$@"; do
  case "$arg" in
    --no-open) OPEN_BROWSER=0 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

if [ -t 1 ]; then
  BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
else
  BOLD=""; RED=""; GREEN=""; YELLOW=""; RESET=""
fi

info() { printf '%s==>%s %s\n' "$BOLD" "$RESET" "$*"; }
ok() { printf '%s ✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '%s !%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
fail() { printf '%s ✗%s %s\n' "$RED" "$RESET" "$*" >&2; }

# Read by docker-compose.yml.
export BACKEND_PORT API_PORT FRONTEND_PORT

compose() {
  docker compose --project-directory "$SYSTEM_ROOT" -f "$SYSTEM_ROOT/docker-compose.yml" \
    --env-file "$SYSTEM_ROOT/.env.${DBT_TARGET:-nonprod}" "$@"
}

problems=0

if ! command -v docker >/dev/null; then
  fail "Docker is required. Install Docker Desktop: https://docs.docker.com/get-docker/"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  fail "Docker Compose v2 is required (the \`docker compose\` command)."
  problems=1
fi
if ! docker info >/dev/null 2>&1; then
  fail "Docker is not running. Start Docker Desktop and try again."
  problems=1
fi
command -v curl >/dev/null || { fail "curl is required."; problems=1; }

if [ "$problems" -ne 0 ]; then
  exit 1
fi

ENV_FILE="$SYSTEM_ROOT/.env.${DBT_TARGET:-nonprod}"
if ! grep -Eq '^REMY_POSTGRES_PASSWORD=.+' "$ENV_FILE" 2>/dev/null; then
  fail "Set REMY_POSTGRES_PASSWORD in $ENV_FILE. The database will not start without it."
  printf '   To make one: openssl rand -hex 24\n' >&2
  exit 1
fi

if [ -n "$(compose ps --status running --quiet 2>/dev/null)" ]; then
  fail "Remy is already running in Docker."
  printf '   Press Ctrl+C in the terminal running ./start-all.sh, or run: (cd %q && docker compose down)\n' "$SYSTEM_ROOT" >&2
  exit 1
fi

# A port that is already taken (by another program or another container) is
# swapped for the next free one, so the stack still starts. Ports already
# picked are skipped too, so two services never land on the same one.
port_busy() {
  if command -v lsof >/dev/null; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
  fi
}

taken=" "
pick_port() {
  local var=$1 label=$2 port=${!1} start=${!1}
  while port_busy "$port" || [[ "$taken" == *" $port "* ]]; do
    port=$((port + 1))
    if [ "$port" -gt 65535 ] || [ $((port - start)) -gt 100 ]; then
      fail "No free port found for the $label from $start to $((port - 1))."
      exit 1
    fi
  done
  [ "$port" = "$start" ] || warn "Port $start ($label) is in use, using $port instead."
  printf -v "$var" '%s' "$port"
  taken="$taken$port "
}

pick_port BACKEND_PORT "auth backend"
pick_port API_PORT "Remy API"
pick_port FRONTEND_PORT "frontend"

grep -Eq '^REMY_JWT_SECRET=.+' "$ENV_FILE" 2>/dev/null ||
  warn "REMY_JWT_SECRET is not set in $ENV_FILE, so everyone is signed out whenever the backend restarts."

banner() {
  echo
  info "Remy is running"
  printf '    Frontend      http://localhost:%s\n' "$FRONTEND_PORT"
  printf '    Auth backend  http://localhost:%s/docs\n' "$BACKEND_PORT"
  printf '    Remy API      http://localhost:%s/docs\n' "$API_PORT"
  printf '    Live logs follow. Press Ctrl+C to stop everything.\n\n'
}

stop_all() {
  echo
  info "Stopping containers…"
  compose down >/dev/null 2>&1 && ok "All containers stopped."
}

interrupted=0
trap 'interrupted=1' INT TERM

info "Starting Remy in Docker (auth backend :$BACKEND_PORT, API :$API_PORT, frontend :$FRONTEND_PORT)"
info "The first run builds the images and takes a few minutes."

if ! compose up --build --detach --wait --wait-timeout 900 --remove-orphans; then
  if [ "$interrupted" -eq 0 ]; then
    echo
    fail "Remy did not start. The last log lines from each service:"
    compose ps --all
    compose logs --tail 30
  fi
  stop_all
  exit 1
fi
[ "$interrupted" -eq 0 ] || { stop_all; exit 130; }

banner
if [ "$OPEN_BROWSER" -eq 1 ]; then
  if command -v open >/dev/null; then
    open "http://localhost:$FRONTEND_PORT"
  elif command -v xdg-open >/dev/null; then
    xdg-open "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1
  fi
fi

# `compose logs --follow` quits whenever a container is removed (for example a
# `docker compose run --rm`), so it is restarted rather than trusted as a
# sign that the stack has stopped.
follow_logs() {
  compose logs --follow --tail 0 &
  LOGS=$!
}
follow_logs

failed=0
while [ "$interrupted" -eq 0 ]; do
  stopped=$(compose ps --all --status exited --status dead --format '{{.Service}}' \
    postgres backend api frontend 2>/dev/null | tr '\n' ' ')
  if [ -n "${stopped// /}" ]; then
    fail "Stopped unexpectedly: $stopped. Shutting down the others."
    failed=1
    break
  fi
  kill -0 "$LOGS" 2>/dev/null || follow_logs
  sleep 2
done

kill "$LOGS" 2>/dev/null
wait "$LOGS" 2>/dev/null
stop_all
exit "$failed"
