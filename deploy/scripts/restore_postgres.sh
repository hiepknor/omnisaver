#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 backups/postgres/omnisaver-YYYYMMDDTHHMMSSZ.sql.gz" >&2
  exit 2
fi

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker/docker-compose.production.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env}"
BACKUP_FILE="$1"

gzip -dc "${BACKUP_FILE}" \
  | docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" exec -T postgres \
      sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
