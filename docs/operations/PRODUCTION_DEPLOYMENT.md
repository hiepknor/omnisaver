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

The production template is `deploy/docker/docker-compose.production.example.yml`.
Copy it before editing local production settings:

```bash
cp deploy/docker/docker-compose.production.example.yml deploy/docker/docker-compose.production.yml
```

The template builds the bot, web, and worker images from local Dockerfiles, keeps PostgreSQL and Redis on an internal network, exposes only Nginx, and enables health checks, restart policy, and bounded container logs.

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
mkdir -p deploy/certs

# 4. create compose file
cp deploy/docker/docker-compose.production.example.yml deploy/docker/docker-compose.production.yml

# 5. validate production config
docker compose -f deploy/docker/docker-compose.production.yml config

# 6. start production stack
docker compose -f deploy/docker/docker-compose.production.yml up -d

# 7. inspect logs
docker compose -f deploy/docker/docker-compose.production.yml logs -f
```

## Reverse Proxy

The example Nginx config in `deploy/docker/nginx.example.conf`:

- redirects HTTP to HTTPS;
- proxies `https://omnisaver.example.com` to the web service on port 8000;
- applies per-IP request and connection limits;
- sets basic security headers.

Replace `omnisaver.example.com` and mount real certificate files:

```text
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

## Backups

Back up PostgreSQL daily.

Do not back up temporary download files unless intentionally required.

Manual backup:

```bash
deploy/scripts/admin.sh backup
```

Manual restore:

```bash
deploy/scripts/admin.sh restore backups/postgres/omnisaver-YYYYMMDDTHHMMSSZ.sql.gz
```

## Updates

```bash
git pull
docker compose -f deploy/docker/docker-compose.production.yml build
docker compose -f deploy/docker/docker-compose.production.yml up -d
```

## Health And Metrics

```bash
deploy/scripts/admin.sh health
deploy/scripts/admin.sh metrics
```

Metrics include container status, one-shot Docker stats, Redis queue length, and PostgreSQL database size.

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
