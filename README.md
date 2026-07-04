# OmniSaver

OmniSaver is a Telegram bot platform for downloading media from public links and user-authorized private links.

Implementation is in progress. The repository currently contains the Python monorepo foundation, public URL detection and download job building blocks, async worker persistence, and the first web session portal/vault layer.

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
| Instagram | gallery-dl, Instaloader | yt-dlp |
| Pinterest | gallery-dl | yt-dlp |
| Facebook | yt-dlp | none initially |
| TikTok | yt-dlp | none initially |
| YouTube | yt-dlp | none initially |
| X/Twitter | yt-dlp, gallery-dl | none initially |
| Reddit | yt-dlp, gallery-dl | none initially |
| Generic URL | yt-dlp | none initially |

## Repository Status

Current status: **Phase 5 — Web Session Portal and Vault implemented**.

The next milestone is `Phase 6 — Authenticated Downloads` in `docs/engineering/DEVELOPMENT_ROADMAP.md`.

## Core Documents

- `AGENTS.md` — instructions for Codex/AI coding agents.
- `docs/product/PRODUCT_REQUIREMENTS.md` — product scope and behavior.
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
- Telegram sender protocol for mocked tests and later real Telegram integration.
- Bot-side helper that turns the first URL in a message into a public download job.

The current implementation does not yet include real Telegram command handlers. Those belong to later phases.

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

## Web Session Portal And Vault

Phase 5 adds the first session connection layer:

- FastAPI portal routes for `/health`, `/connect/{platform}`, and `/disconnect/{platform}`.
- One-time connect tokens bound to a Telegram user and platform.
- Token expiration and one-time-use enforcement.
- AES-256-GCM session encryption in `omnisaver_session_vault`.
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
.venv/bin/python -m omnisaver_web
```

The current portal validates supported platform and payload shape only. It does not download private media or bypass platform access controls; authenticated downloads are planned for Phase 6.
