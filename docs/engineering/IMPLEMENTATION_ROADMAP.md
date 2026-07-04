# Implementation Roadmap

This document defines the phase sequence. Use `docs/engineering/DEVELOPMENT_ROADMAP.md` to track progress with checkboxes.

## Phase 0 — Planning Scaffold

Status: complete.

Deliverables:

- README
- AGENTS.md
- Product requirements
- System design
- Functional spec
- Command spec
- Internal API spec
- Security model
- Database spec
- Testing strategy
- Production deployment guide
- Operations runbook

No application code in this phase.

## Phase 1 — Repository Foundation

Goal: create a runnable, testable Python project skeleton without downloader logic.

Deliverables:

- Python 3.11 project structure.
- Package boundaries matching `AGENTS.md`.
- Test runner, formatter, linter, and type-check configuration.
- Typed config loader.
- Docker build skeleton.
- Local Docker Compose skeleton.
- README setup, test, and run commands.

Acceptance criteria:

- Project installs locally.
- Tests run successfully.
- Formatting, linting, and type checks run successfully.
- Docker Compose validates or boots the foundation services.
- No downloader, session, or private-content logic is introduced.

## Phase 2 — URL Detection

Goal: deterministic URL extraction and platform detection.

Deliverables:

- URL extraction from Telegram messages.
- Platform detector.
- Safe unsupported URL error.
- Unit tests for all supported platform patterns.

Acceptance criteria:

- Instagram, Pinterest, Facebook, TikTok, YouTube, X/Twitter, Reddit, and generic URLs are detected deterministically.
- Unsupported or malformed URLs return safe errors.
- URL detection has focused unit coverage.

## Phase 3 — Public Download MVP

Goal: working Telegram bot for public links.

Deliverables:

- Bot service.
- URL detector.
- Basic downloader manager.
- yt-dlp integration.
- gallery-dl integration for Pinterest/Instagram public links.
- Temporary storage.
- Telegram media sender.
- Cleanup after send.

Acceptance criteria:

- User can send one public URL.
- Bot downloads media.
- Bot sends media back.
- Unsupported URLs return clear error.
- Temporary files are removed.

## Phase 4 — Async Worker and Persistence

Goal: make downloads reliable and non-blocking.

Deliverables:

- PostgreSQL schema.
- Redis queue.
- Download worker.
- Job status updates.
- Job history.
- Retry policy.

Acceptance criteria:

- Bot handler never blocks on long downloads.
- Jobs survive bot restart if queued/persisted.
- Failed jobs are recorded with safe errors.

## Phase 5 — Web Session Portal and Vault

Goal: support user-authorized session-based downloads.

Deliverables:

- FastAPI web portal.
- One-time connect tokens.
- Session validation.
- Session encryption.
- `/sessions` and `/disconnect`.

Acceptance criteria:

- Each user can connect one session per platform.
- Session is encrypted at rest.
- Private/auth-required link uses only the requesting user's session.
- User can revoke session.

## Phase 6 — Authenticated Downloads

Goal: safely use user-owned sessions for auth-required links.

Deliverables:

- Requesting-user session lookup.
- Session ownership enforcement.
- Session-aware downloader invocation.
- Auth error normalization.
- Security tests for cross-user isolation.

Acceptance criteria:

- Authenticated downloads use only the requesting user's session.
- Missing, expired, revoked, or unauthorized sessions return safe errors.
- No shared platform account fallback exists.

## Phase 7 — Multi-Engine Platform Adapters

Goal: increase reliability.

Deliverables:

- Instagram adapter: gallery-dl, Instaloader, yt-dlp fallback.
- Pinterest adapter: gallery-dl, yt-dlp fallback.
- Facebook adapter: yt-dlp.
- TikTok adapter: yt-dlp.
- YouTube adapter: yt-dlp.
- X/Twitter adapter: yt-dlp, gallery-dl fallback.
- Reddit adapter: gallery-dl, yt-dlp fallback.
- Generic adapter: yt-dlp.
- Engine error normalization.

Acceptance criteria:

- Adapter selection is deterministic.
- Fallback runs only when safe and configured.
- Errors are mapped to standard error codes.

## Phase 8 — Media Processing and Limits

Goal: robust Telegram delivery.

Deliverables:

- FFmpeg compression.
- Thumbnail generation.
- Media group support.
- Oversize handling.
- Configurable size/quality limits.

Acceptance criteria:

- Large videos are compressed or rejected safely.
- Carousels are sent cleanly.
- User sees useful file-size errors.

## Phase 9 — Production Hardening

Goal: safe VPS production.

Deliverables:

- Docker Compose production profile.
- Caddy reverse proxy guide.
- HTTPS instructions.
- Backups.
- Metrics/logging.
- Request limits and rate-limit strategy.
- Admin maintenance commands.

Acceptance criteria:

- Server can be deployed from a clean VPS.
- Restart policy works.
- Backups are documented.
- Secrets are not committed.

## Phase 10 — Runtime Integration

Goal: replace test-only wiring with production runtime dependencies.

Deliverables:

- PostgreSQL session repository for connect tokens and encrypted sessions.
- Web session portal runtime wired to PostgreSQL.
- Bot command handlers wired to Redis queue and session commands.
- Downloader worker runtime wired to Redis, PostgreSQL, downloader engines, media processor, session resolver, and Telegram sender.
- End-to-end public and authenticated download checks against running services.

Acceptance criteria:

- Web connect tokens and encrypted sessions survive web service restarts.
- Bot enqueues jobs without downloading in request handlers.
- Worker processes queued jobs and records safe status in PostgreSQL.
- Authenticated downloads use only the requesting user's PostgreSQL-backed encrypted session.
- No session payload, cookie, token, or secret is logged or stored in plaintext.
