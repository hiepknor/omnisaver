#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker/docker-compose.production.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env}"
QUEUE_NAME="${QUEUE_NAME:-omnisaver:download_jobs}"

echo "# containers"
docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" ps

echo "# docker stats"
docker stats --no-stream

echo "# redis queue length"
docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" exec -T redis redis-cli llen "${QUEUE_NAME}"

echo "# postgres database size"
docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB" -tAc "select pg_size_pretty(pg_database_size(current_database()));"'
