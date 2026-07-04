# OmniSaver

OmniSaver is a Telegram bot platform for downloading media from public links and user-authorized private links.

Implementation has not started yet. The repository currently contains product, architecture, security, and engineering docs that define how the system should be built.

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

Current status: **Phase 3 — Public Download MVP implemented**.

The next milestone is `Phase 4 — Async Worker and Persistence` in `docs/engineering/DEVELOPMENT_ROADMAP.md`.

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

The app containers are skeletons in Phase 1 and are available behind the `apps` Compose profile:

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

The current implementation does not yet include Redis, PostgreSQL persistence, or real Telegram command handlers. Those belong to later phases.
