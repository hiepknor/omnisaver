#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker/docker-compose.production.yml}"

docker compose -f "${COMPOSE_FILE}" ps
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose -f "${COMPOSE_FILE}" exec -T redis redis-cli ping
docker compose -f "${COMPOSE_FILE}" exec -T worker python -m omnisaver_worker health
