# Production Deployment Guide

This guide describes the intended production deployment on a VPS/server using Docker.

## Target Server

Minimum recommended:

- Ubuntu 22.04/24.04/26.04 LTS-style server
- 2 vCPU
- 4 GB RAM
- 30 GB SSD
- Docker + Docker Compose
- Domain name with HTTPS

Recommended:

- 4 vCPU
- 8 GB RAM
- 80 GB SSD

## Services

```text
nginx / reverse proxy
bot service
web portal
worker service
postgres
redis
cleanup worker
```

## Environment

Create `.env` from `.env.example` and fill:

```text
TELEGRAM_BOT_TOKEN=
PUBLIC_BASE_URL=https://your-domain.com
DATABASE_URL=
REDIS_URL=
SESSION_VAULT_MASTER_KEY_BASE64=
```

Generate a strong session vault key before production.

## Docker Compose Template

The file in `deploy/docker/docker-compose.production.example.yml` is a template. It intentionally references images/services that will be implemented in later phases.

## Deployment Steps

```bash
# 1. clone repo
git clone <repo-url>
cd omnisaver

# 2. create env
cp .env.example .env
nano .env

# 3. create persistent directories
mkdir -p storage/downloads
mkdir -p backups/postgres

# 4. start production stack after code exists
docker compose -f deploy/docker/docker-compose.production.yml up -d

# 5. inspect logs
docker compose -f deploy/docker/docker-compose.production.yml logs -f
```

## Reverse Proxy

Route:

```text
https://omnisaver.example.com -> web service port 8000
```

Telegram webhook route can be served by the bot service or through the web service depending on implementation.

## Backups

Back up PostgreSQL daily.

Do not back up temporary download files unless intentionally required.

## Updates

```bash
git pull
docker compose -f deploy/docker/docker-compose.production.yml build
docker compose -f deploy/docker/docker-compose.production.yml up -d
```

## Rollback

Keep previous Docker images or Git tags.

```bash
git checkout <previous-tag>
docker compose -f deploy/docker/docker-compose.production.yml up -d --build
```

## Monitoring

Minimum:

- Container health checks.
- Disk usage alerts.
- Worker queue length.
- Failed job rate.
- PostgreSQL backup success.

## Security Notes

- Never expose PostgreSQL publicly.
- Never expose Redis publicly.
- Use HTTPS for web portal.
- Keep `.env` private.
- Rotate session vault key if compromise is suspected.
