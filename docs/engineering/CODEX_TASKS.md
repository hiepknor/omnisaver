# Codex Task Backlog

Use these as implementation prompts.

## Task 1 — Initialize Python Project

Create a Python 3.11 project structure matching the architecture. Add no downloader logic yet. Include config loading, test setup, and Docker build skeleton.

## Task 2 — URL Detector

Implement URL detection for Instagram, Pinterest, Facebook, TikTok, YouTube, X/Twitter, Reddit, and generic links. Add unit tests.

## Task 3 — Public Download MVP

Implement public download job flow using yt-dlp and gallery-dl wrappers. Mock Telegram sender in tests.

## Task 4 — Redis Worker

Move download execution to an async worker backed by Redis. Add job status persistence.

## Task 5 — Database Models

Implement PostgreSQL models and migrations according to `docs/specs/DATABASE_SPEC.md`.

## Task 6 — Session Vault

Implement encrypted session storage with ownership checks and no secret logging.

## Task 7 — Web Connect Portal

Implement FastAPI portal for one-time connect tokens and session validation.

## Task 8 — Authenticated Download

Use only the requesting user's session for auth-required links. Add tests proving cross-user isolation.

## Task 9 — Production Docker

Create final Dockerfiles and production compose file. Update deployment docs with exact commands.

## Task 10 — Hardening

Add rate limits, cleanup worker, metrics, and runbook commands.
