# Production Deployment Guide

This guide describes the intended production deployment on a VPS/server using Docker.

## Target Server

Current deployment target:

```text
ssh ubuntu@43.153.208.222
deploy path: /opt/omnisaver
domain: https://omnisaver.onio.cc
```

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
caddy / reverse proxy
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
PUBLIC_BASE_URL=https://omnisaver.onio.cc
DATABASE_URL=
REDIS_URL=
WORKER_POLL_SECONDS=1
SESSION_VAULT_MASTER_KEY_BASE64=
```

Generate a strong session vault key before production.

## Docker Compose Template

The production template is `deploy/docker/docker-compose.production.example.yml`.
Copy it before editing local production settings:

```bash
cp deploy/docker/docker-compose.production.example.yml deploy/docker/docker-compose.production.yml
```

The template builds the bot, web, and worker images from local Dockerfiles, keeps PostgreSQL and Redis on an internal network, exposes only Caddy, and enables health checks, restart policy, and bounded container logs.

The bot image installs `python-telegram-bot` from pinned project dependencies and runs long polling by default. Its health check uses `python -m omnisaver_bot health`, which does not contact Telegram.

The worker image installs FFmpeg from the OS package manager and the pinned Python CLI engines from project dependencies: `yt-dlp`, `gallery-dl`, and `instaloader`. Override `YTDLP_BIN`, `GALLERY_DL_BIN`, `INSTALOADER_BIN`, or `FFMPEG_BIN` only when mounting custom binaries.

The bot, web, worker, and cleanup worker are attached to both the private app network and a normal Docker bridge network. PostgreSQL and Redis stay private, while application containers still have outbound internet access for Telegram and downloader engines.

## Deployment Steps

```bash
# 1. clone repo
sudo mkdir -p /opt/omnisaver
sudo chown ubuntu:ubuntu /opt/omnisaver
git clone https://github.com/hiepknor/omnisaver.git /opt/omnisaver
cd /opt/omnisaver

# 2. create env
cp .env.example .env
nano .env

# 3. create persistent directories
mkdir -p storage/downloads
mkdir -p backups/postgres

# 4. create compose file
cp deploy/docker/docker-compose.production.example.yml deploy/docker/docker-compose.production.yml

# 5. validate production config
docker compose --env-file .env -f deploy/docker/docker-compose.production.yml config

# 6. start database and queue
docker compose --env-file .env -f deploy/docker/docker-compose.production.yml up -d postgres redis

# 7. apply database schema
deploy/scripts/admin.sh migrate

# 8. start production stack
docker compose --env-file .env -f deploy/docker/docker-compose.production.yml up -d

# 9. inspect logs
docker compose --env-file .env -f deploy/docker/docker-compose.production.yml logs -f
```

To smoke-check the downloader worker against the configured Redis queue and PostgreSQL database, run one job-processing attempt:

```bash
docker compose --env-file .env -f deploy/docker/docker-compose.production.yml run --rm worker \
  python -m omnisaver_worker process-once
```

## Reverse Proxy

The example Caddy config in `deploy/docker/Caddyfile.example`:

- obtains and renews HTTPS certificates automatically;
- proxies `https://omnisaver.onio.cc` to the web service on port 8000;
- limits request body size to 2 MB;
- sets basic security headers.

The example is already configured for `omnisaver.onio.cc`. Change the domain only if the production host changes. Caddy stores ACME state in the `caddy_data` and `caddy_config` Docker volumes. An ACME contact email is optional; add a global `email` option to the Caddyfile only if you want certificate authority notifications.

Caddy core does not provide per-IP request rate limiting. If hard rate limits are required, enforce them with a Caddy build that includes a rate-limit plugin, or place a firewall/CDN/load balancer rate limit in front of Caddy.

If Caddy is already installed on the host and owns ports 80/443, use the host-Caddy override instead of the Caddy container:

```bash
docker compose --env-file .env \
  -f deploy/docker/docker-compose.production.yml \
  -f deploy/docker/docker-compose.host-caddy.yml \
  up -d postgres redis bot web worker
```

Then add this site block to the host Caddyfile and reload Caddy:

```caddyfile
omnisaver.onio.cc {
	encode zstd gzip
	request_body {
		max_size 2MB
	}
	reverse_proxy 127.0.0.1:8000
	header {
		X-Content-Type-Options nosniff
		X-Frame-Options DENY
		Referrer-Policy no-referrer
		Permissions-Policy "geolocation=(), microphone=(), camera=()"
	}
}
```

## Telegram Webhook

The current bot runtime uses Telegram long polling through `python-telegram-bot`, so no Telegram webhook setup is required. Leave `TELEGRAM_WEBHOOK_URL` empty.

If the bot is later changed to webhook mode, add a public FastAPI webhook endpoint, expose it through Caddy, set `TELEGRAM_WEBHOOK_URL=https://omnisaver.onio.cc/<webhook-path>`, and register it with Telegram:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$TELEGRAM_WEBHOOK_URL"
```

## Backups

Back up PostgreSQL daily.

Do not back up temporary download files unless intentionally required.

Manual backup:

```bash
deploy/scripts/admin.sh migrate
deploy/scripts/admin.sh backup
```

Manual restore:

```bash
deploy/scripts/admin.sh restore backups/postgres/omnisaver-YYYYMMDDTHHMMSSZ.sql.gz
```

## Updates

```bash
git pull
docker compose --env-file .env -f deploy/docker/docker-compose.production.yml build
docker compose --env-file .env -f deploy/docker/docker-compose.production.yml up -d
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
docker compose --env-file .env -f deploy/docker/docker-compose.production.yml up -d --build
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
