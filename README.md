# OmniSaver

OmniSaver is a Telegram bot platform for downloading media from public links and user-authorized private links.

Implementation is in progress. The repository currently contains the Python monorepo foundation, public URL detection and download job building blocks, Telegram bot command handlers, async worker persistence, the web session portal/vault layer with PostgreSQL-backed runtime storage, authenticated download session enforcement, deterministic multi-engine adapter selection, media processing limits, and production deployment hardening.

## Goals

- Download photos and videos from supported platforms.
- Support public links first.
- Support authenticated links only when the Telegram user owns or provides a valid session that has permission to view the content.
- Keep one isolated session per Telegram user and platform.
- Avoid bypassing privacy controls or accessing content without authorization.
- Deploy to production using Docker on a VPS/server.

## Supported Platform Targets

| Platform | Primary Engine | Fallback |
|---|---|---|
| Instagram | gallery-dl | Instaloader, yt-dlp |
| Pinterest | gallery-dl | yt-dlp |
| Facebook | yt-dlp | none initially |
| TikTok | yt-dlp | none initially |
| YouTube | yt-dlp | none initially |
| X/Twitter | yt-dlp | gallery-dl |
| Reddit | gallery-dl | yt-dlp |
| Generic URL | yt-dlp | none initially |

## Repository Status

Current status: **Phase 10 — Runtime Integration implemented**.

The roadmap checklist in `docs/engineering/DEVELOPMENT_ROADMAP.md` is implemented through Phase 10, including service-backed E2E checks for public and authorized download flows through local PostgreSQL and Redis.

## Core Documents

- `AGENTS.md` — instructions for Codex/AI coding agents.
- `docs/product/PRODUCT_REQUIREMENTS.md` — product scope and behavior.
- `docs/product/UX_UPGRADE_PLAN.md` — user experience audit follow-up plan.
- `docs/architecture/SYSTEM_DESIGN.md` — system architecture.
- `docs/specs/FUNCTIONAL_SPEC.md` — feature-level requirements.
- `docs/specs/API_SPEC.md` — internal API contracts.
- `docs/security/SECURITY_MODEL.md` — session vault, cookies, privacy and abuse rules.
- `docs/engineering/IMPLEMENTATION_ROADMAP.md` — phased implementation plan.
- `docs/engineering/DEVELOPMENT_ROADMAP.md` — implementation checklist and progress tracker.
- `docs/operations/PRODUCTION_DEPLOYMENT.md` — Docker production deployment guide.

## Non-Goals

- No private-content bypass.
- No credential phishing.
- No scraping content that the user cannot access legitimately.
- No resale of downloaded content.
- No storing user cookies in plaintext.

## Intended Production Components

```text
omnisaver/
├─ apps/
│  ├─ bot/                 # Telegram bot service
│  └─ web/                 # Web session portal
├─ workers/
│  └─ downloader/          # Download workers
├─ packages/
│  ├─ downloader/          # Platform adapters
│  ├─ session-vault/       # Encryption/decryption
│  ├─ db/                  # Database access
│  └─ media-processor/     # FFmpeg helpers
├─ deploy/
│  └─ docker/              # Production deployment templates and docs
├─ config/                 # Shared typed configuration loader
├─ docs/
└─ storage/
```

## Local Development

Create a virtual environment and install dev tooling:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

Run checks:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
docker compose -f deploy/docker/docker-compose.local.yml config
```

Start local foundation services:

```bash
cp .env.example .env
docker compose -f deploy/docker/docker-compose.local.yml up -d postgres redis
docker compose -f deploy/docker/docker-compose.local.yml ps
docker compose -f deploy/docker/docker-compose.local.yml down
```

The app containers are available behind the `apps` Compose profile:

```bash
docker compose -f deploy/docker/docker-compose.local.yml --profile apps build
```

Run service-backed E2E checks against local PostgreSQL and Redis:

```bash
docker compose -f deploy/docker/docker-compose.local.yml up -d postgres redis
OMNISAVER_RUN_SERVICE_E2E=1 .venv/bin/python -m pytest tests/test_e2e_services.py
```

## URL Detection

Phase 2 provides a deterministic URL detector in `omnisaver_downloader`:

```python
from omnisaver_downloader import detect_url, extract_urls

urls = extract_urls("Save https://www.instagram.com/reel/abc123/")
detected = detect_url(urls[0])
```

Supported detection targets: Instagram, Pinterest, Facebook, TikTok, YouTube, X/Twitter, Reddit, and generic HTTP(S) URLs.

## Public Download MVP

Phase 3 adds testable public-download building blocks:

- Downloader contracts for normalized `MediaResult` and `MediaFile` objects.
- `yt-dlp` and `gallery-dl` subprocess wrappers.
- Deterministic platform adapter selection and safe retryable fallback.
- Public download job runner with temporary storage cleanup.
- Telegram sender protocol for mocked tests and worker delivery.
- Bot-side helper that turns the first URL in a message into a public download job.

The real Telegram command handlers are wired in the Phase 10 bot runtime section below.

## Async Worker And Persistence

Phase 4 adds queue and persistence building blocks:

- PostgreSQL migration SQL in `packages/db/migrations/001_initial.sql`.
- Download job repository contract plus PostgreSQL and in-memory implementations.
- Redis-backed job queue abstraction and in-memory queue for tests.
- Worker service that dequeues jobs, records status, applies retry policy, and stores safe failures.
- Bot-side enqueue helper that creates a job and returns immediately.

Apply the initial schema to a running PostgreSQL database:

```bash
psql "$DATABASE_URL" -f packages/db/migrations/001_initial.sql
```

Run local Redis/PostgreSQL services:

```bash
cp .env.example .env
docker compose -f deploy/docker/docker-compose.local.yml up -d postgres redis
```

Redis uses a list queue named `omnisaver:download_jobs`. The local Compose Redis service enables append-only storage so queued jobs can survive Redis container restarts.

## Bot Runtime

Phase 10 wires the Telegram bot entrypoint to `python-telegram-bot`:

- `/start` and `/help` return the command-spec text and privacy rule.
- `/connect_instagram`, `/connect_pinterest`, and `/connect_facebook` create one-time web portal links.
- `/sessions` reads PostgreSQL-backed session status.
- `/disconnect <platform>` revokes the requesting user's session.
- `/history` reads recent job status for the Telegram user.
- Plain text messages enqueue the first supported URL into Redis and return a job id.

The bot handler path does not download media directly. It only validates/extracts the URL, enqueues a job, and returns status text.

Run the bot locally after setting `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `REDIS_URL`, and `PUBLIC_BASE_URL`:

```bash
.venv/bin/python -m omnisaver_bot
```

## Web Session Portal And Vault

Phase 5 adds the first session connection layer:

- FastAPI portal routes for `/health`, `/connect/{platform}`, and `/disconnect/{platform}`.
- One-time connect tokens bound to a Telegram user and platform.
- Token expiration and one-time-use enforcement.
- AES-256-GCM session encryption in `omnisaver_session_vault`.
- PostgreSQL-backed runtime storage for connect tokens and encrypted user sessions.
- Bot helpers for connect links, `/sessions` status text, and `/disconnect` behavior.
- Tests for session ownership, revocation, expired tokens, encrypted storage, and no plaintext session logging.

Generate a local session vault key:

```bash
.venv/bin/python -c "from omnisaver_session_vault import SessionVault; print(SessionVault.generate_master_key_base64())"
```

Set the key before running the web app:

```bash
export SESSION_VAULT_MASTER_KEY_BASE64="<generated-32-byte-base64-key>"
export COOKIE_ENCRYPTION_KEY_ID="local-dev"
export DATABASE_URL="postgresql://omnisaver:omnisaver@localhost:5432/omnisaver"
.venv/bin/python -m omnisaver_web
```

The current portal validates supported platform and payload shape only. It does not download private media or bypass platform access controls.

Phase 10 adds an integration test that connects a session through the web portal, stores it encrypted, and resolves it through the worker `VaultSessionResolver` for the same Telegram user while rejecting another user.

## Authenticated Download Enforcement

Phase 6 adds the safe authenticated-download path:

- Worker resolves sessions by `telegram_user_id` and platform only.
- Revoked, missing, and expired sessions fail with safe `SESSION_*` errors.
- Public downloads that return `LOGIN_REQUIRED` can retry through the authenticated path.
- Job payloads carry only `requires_auth`; they do not carry cookies, tokens, or encrypted session payloads.
- The session vault decrypts stored session payloads only inside the authorized worker flow.
- Engine output that indicates forbidden access maps to `ACCESS_DENIED`.

Authenticated invocation is wired and tested. Engine adapters do not write plaintext cookie files or inject sessions into subprocess commands.

## Multi-Engine Platform Adapters

Phase 7 adds deterministic adapter selection and safe fallback rules:

- Instagram: `gallery-dl`, then `instaloader`, then `yt-dlp`.
- Pinterest: `gallery-dl`, then `yt-dlp`.
- Facebook, TikTok, YouTube, and generic URLs: `yt-dlp`.
- X/Twitter: `yt-dlp`, then `gallery-dl`.
- Reddit: `gallery-dl`, then `yt-dlp`.

Fallback only happens for errors explicitly marked safe for fallback. Login-required, access-denied, rate-limited, unsupported, oversized, and session errors do not cascade into another engine.

Configure engine binary names or paths through:

```bash
YTDLP_BIN=yt-dlp
GALLERY_DL_BIN=gallery-dl
INSTALOADER_BIN=instaloader
```

The Python package installs pinned CLI engine dependencies for these commands: `yt-dlp`, `gallery-dl`, and `instaloader`.

## Media Processing And Limits

Phase 8 adds a media processor boundary before Telegram sending:

- Videos can be compressed through FFmpeg when they exceed the configured max file size.
- Video thumbnails are generated through FFmpeg when possible.
- Multi-file results are marked as media groups through result metadata.
- Oversized non-video files are rejected with `MEDIA_TOO_LARGE`.
- Temporary files use per-user layout: `storage/downloads/<telegram_user_id>/<job_id>`.
- Expired temporary files can be removed with `cleanup_expired_temp_files`.

Relevant environment variables:

```bash
MAX_DOWNLOAD_SIZE_MB=2000
MEDIA_MAX_TEMP_STORAGE_MB=5000
MEDIA_VIDEO_CRF=28
MEDIA_VIDEO_MAX_HEIGHT=720
MEDIA_THUMBNAIL_WIDTH=320
FFMPEG_BIN=ffmpeg
```

## Downloader Worker Runtime

Phase 10 wires the downloader worker entrypoint to production dependencies:

- Redis queue `omnisaver:download_jobs`.
- PostgreSQL download job repository.
- PostgreSQL-backed session resolver plus session vault.
- Multi-engine downloader manager.
- FFmpeg media processor.
- Telegram Bot API media sender.

The default worker command runs continuously and polls Redis when the queue is empty. For maintenance or smoke checks, process at most one queued job:

```bash
.venv/bin/python -m omnisaver_worker process-once
```

Relevant environment variables:

```bash
TELEGRAM_BOT_TOKEN=
DATABASE_URL=postgresql://omnisaver:change-me@localhost:5432/omnisaver
REDIS_URL=redis://localhost:6379/0
SESSION_VAULT_MASTER_KEY_BASE64=
COOKIE_ENCRYPTION_KEY_ID=default
WORKER_POLL_SECONDS=1
```

## Production Hardening

Phase 9 adds production deployment artifacts:

- Non-root app containers and FFmpeg in the worker image.
- Production Docker Compose template with internal networks, restart policy, health checks, bounded logs, Caddy, and maintenance profile.
- Caddy HTTPS reverse-proxy example with automatic certificate management, request body limits, and security headers.
- Admin scripts for health, metrics, cleanup, backup, restore, and logs.

Validate the production compose template:

```bash
POSTGRES_DB=omnisaver \
POSTGRES_USER=omnisaver \
POSTGRES_PASSWORD=change-me \
docker compose -f deploy/docker/docker-compose.production.example.yml config
```

Common admin commands:

```bash
deploy/scripts/admin.sh health
deploy/scripts/admin.sh metrics
deploy/scripts/admin.sh backup
deploy/scripts/admin.sh cleanup
```
