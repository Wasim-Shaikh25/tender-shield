#!/usr/bin/env bash
# Verify that OpenTelemetry traces from the TenderShield backend land in Jaeger.
#
# Usage:
#   ./scripts/verify-traces.sh
#
# This script:
# 1. Starts a temporary Jaeger all-in-one container.
# 2. Starts the backend with TS_OTEL_ENABLED=true pointing at Jaeger.
# 3. Calls /api/health to generate a trace.
# 4. Polls Jaeger until the trace is visible, then prints the UI URL.

set -e

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
JAEGER_UI="http://localhost:16686"
QUERY_URL="http://localhost:16686/api/services"
OTEL_ENDPOINT="http://localhost:4318/v1/traces"
SERVICE_NAME="tendershield-backend"

cleanup() {
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  docker rm -f jaeger-verify 2>/dev/null || true
}
trap cleanup EXIT

echo "Starting Jaeger..."
docker run -d --name jaeger-verify \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  -e COLLECTOR_OTLP_ENABLED=true \
  jaegertracing/all-in-one:latest >/dev/null

# Wait for Jaeger query API.
for i in $(seq 1 30); do
  if curl -sf "$QUERY_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -sf "$QUERY_URL" >/dev/null 2>&1; then
  echo "Jaeger did not start" >&2
  exit 1
fi

echo "Starting backend with OpenTelemetry enabled..."
cd "$ROOT_DIR/backend"
# shellcheck source=/dev/null
set -a
source "$ROOT_DIR/.env.local"
set +a
TS_OTEL_ENABLED=true \
TS_OTEL_EXPORTER_OTLP_ENDPOINT="$OTEL_ENDPOINT" \
TS_OTEL_SERVICE_NAME="$SERVICE_NAME" \
.venv/bin/uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait for backend health.
for i in $(seq 1 30); do
  if curl -sf "http://localhost:8000/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -sf "http://localhost:8000/api/health" >/dev/null 2>&1; then
  echo "Backend did not start" >&2
  exit 1
fi

echo "Generating traces by calling /api/health ..."
curl -sf "http://localhost:8000/api/health" >/dev/null

# Poll Jaeger until the service shows up and has at least one trace.
echo "Waiting for traces in Jaeger..."
for i in $(seq 1 60); do
  services=$(curl -sf "$QUERY_URL" 2>/dev/null || true)
  if echo "$services" | grep -q "$SERVICE_NAME"; then
    traces=$(curl -sf "http://localhost:16686/api/traces?service=$SERVICE_NAME&limit=1" 2>/dev/null || true)
    if [ -n "$traces" ] && echo "$traces" | grep -q "$SERVICE_NAME"; then
      echo "Success — trace found for service '$SERVICE_NAME'"
      echo "Open Jaeger UI: $JAEGER_UI/search?service=$SERVICE_NAME"
      exit 0
    fi
  fi
  sleep 1
done

echo "Trace not found in Jaeger after 60 seconds" >&2
exit 1
