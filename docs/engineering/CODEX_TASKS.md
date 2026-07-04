# Codex Task Backlog

Use these as implementation prompts. Tasks map to the phases in `docs/engineering/IMPLEMENTATION_ROADMAP.md`.

## Phase 1 Task — Repository Foundation

Create a Python 3.11 project structure matching the architecture. Add no downloader logic yet. Include config loading, test setup, and Docker build skeleton.

## Phase 2 Task — URL Detector

Implement URL detection for Instagram, Pinterest, Facebook, TikTok, YouTube, X/Twitter, Reddit, and generic links. Add unit tests.

## Phase 3 Task — Public Download MVP

Implement public download job flow using yt-dlp and gallery-dl wrappers. Mock Telegram sender in tests.

## Phase 4 Task — Async Worker and Persistence

Implement PostgreSQL models and migrations, move download execution to an async worker backed by Redis, and add job status persistence.

## Phase 5 Task — Web Session Portal and Vault

Implement encrypted session storage, ownership checks, one-time connect tokens, and the FastAPI connection portal.

## Phase 6 Task — Authenticated Download

Use only the requesting user's session for auth-required links. Add tests proving cross-user isolation.

## Phase 7 Task — Multi-Engine Platform Adapters

Implement deterministic adapter selection, safe fallback rules, and normalized engine errors.

## Phase 8 Task — Media Processing and Limits

Add FFmpeg compression, thumbnails, media groups, file-size limits, and cleanup behavior.

## Phase 9 Task — Production Hardening

Create final Dockerfiles and production Compose file. Add rate limits, metrics, backups, runbook commands, and exact deployment docs.
