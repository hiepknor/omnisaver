#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker/docker-compose.production.yml}"
COMMAND="${1:-}"

case "${COMMAND}" in
  backup)
    exec deploy/scripts/backup_postgres.sh
    ;;
  migrate)
    exec deploy/scripts/migrate.sh
    ;;
  restore)
    shift
    exec deploy/scripts/restore_postgres.sh "$@"
    ;;
  cleanup)
    docker compose -f "${COMPOSE_FILE}" run --rm cleanup-worker
    ;;
  health)
    exec deploy/scripts/healthcheck.sh
    ;;
  metrics)
    exec deploy/scripts/metrics.sh
    ;;
  logs)
    docker compose -f "${COMPOSE_FILE}" logs -f
    ;;
  *)
    echo "usage: $0 {backup|migrate|restore <file>|cleanup|health|metrics|logs}" >&2
    exit 2
    ;;
esac
