# Implementation Roadmap

## Phase 0 — Repository Foundation

Status: documentation scaffold.

Deliverables:

- README
- AGENTS.md
- Product requirements
- System design
- Functional spec
- Security model
- Database spec
- Production deployment guide

No application code in this phase.

## Phase 1 — Public Link MVP

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

## Phase 2 — Async Worker and Persistence

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

## Phase 3 — Web Session Portal and Vault

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

## Phase 4 — Multi-Engine Platform Adapters

Goal: increase reliability.

Deliverables:

- Instagram adapter: gallery-dl, Instaloader, yt-dlp fallback.
- Pinterest adapter: gallery-dl, yt-dlp fallback.
- Facebook adapter: yt-dlp.
- Generic adapter: yt-dlp.
- Engine error normalization.

Acceptance criteria:

- Adapter selection is deterministic.
- Fallback runs only when safe and configured.
- Errors are mapped to standard error codes.

## Phase 5 — Media Processing and Limits

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

## Phase 6 — Production Hardening

Goal: safe VPS production.

Deliverables:

- Docker Compose production profile.
- Nginx reverse proxy guide.
- HTTPS instructions.
- Backups.
- Metrics/logging.
- Rate limits.
- Admin maintenance commands.

Acceptance criteria:

- Server can be deployed from a clean VPS.
- Restart policy works.
- Backups are documented.
- Secrets are not committed.
