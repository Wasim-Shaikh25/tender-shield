#!/usr/bin/env bash
# One run script for local development and dev/prod guidance.
# Usage: ./scripts/run.sh [local|dev|prod]   (default: local)

set -e

ENV=${1:-local}
ENV_FILE=".env.${ENV}"
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

cd "$ROOT_DIR"

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing env file: $ENV_FILE" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

case "$ENV" in
local)
    if [ ! -d "backend/.venv" ]; then
        echo "Backend venv not found. Run:" >&2
        echo "  cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e \".[dev]\"" >&2
        exit 1
    fi

    if [ ! -d "frontend/node_modules" ]; then
        echo "Frontend dependencies not found. Run:" >&2
        echo "  cd frontend && npm install" >&2
        exit 1
    fi

    cd backend
    .venv/bin/alembic upgrade head
    cd "$ROOT_DIR"

    (
        cd backend
        .venv/bin/uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
    ) &
    BACKEND_PID=$!
    trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

    cd frontend
    npm run dev
    ;;

dev|prod)
    echo "$ENV run is intended for containerised or managed deploys." >&2
    echo "See docs/deployment.md for $ENV instructions." >&2
    echo "Quick docker compose example:" >&2
    echo "  docker compose --env-file .env.$ENV up --build" >&2
    ;;

*)
    echo "Usage: $0 {local|dev|prod}" >&2
    exit 1
    ;;
esac
