#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker/docker-compose.production.yml}"
MIGRATION_FILE="${MIGRATION_FILE:-packages/db/migrations/001_initial.sql}"

if [ ! -f "${MIGRATION_FILE}" ]; then
  echo "migration file not found: ${MIGRATION_FILE}" >&2
  exit 2
fi

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  < "${MIGRATION_FILE}"
