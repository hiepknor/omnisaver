# OmniSaver Development Roadmap

This checklist tracks implementation progress. Keep it updated after each completed phase or milestone.

## Status Legend

- `[ ]` Not started
- `[x]` Complete

## Phase 0 — Planning Scaffold

- [x] Create README.
- [x] Create AGENTS.md.
- [x] Create product requirements.
- [x] Create system design.
- [x] Create functional specification.
- [x] Create command specification.
- [x] Create internal API specification.
- [x] Create database specification.
- [x] Create security model.
- [x] Create testing strategy.
- [x] Create production deployment guide.
- [x] Create operations runbook.
- [x] Initialize Git repository.
- [x] Configure Git remote.
- [x] Push initial planning scaffold.

## Phase 1 — Repository Foundation

- [x] Create Python 3.11 project structure.
- [x] Create `apps/bot`.
- [x] Create `apps/web`.
- [x] Create `workers/downloader`.
- [x] Create `packages/downloader`.
- [x] Create `packages/session-vault`.
- [x] Create `packages/db`.
- [x] Create `packages/media-processor`.
- [x] Add `pyproject.toml`.
- [x] Add test runner configuration.
- [x] Add formatter and linter configuration.
- [x] Add typed configuration loader.
- [x] Add Docker build skeleton.
- [x] Add local Docker Compose skeleton.
- [x] Update README with exact setup, test, and run commands.

## Phase 2 — URL Detection

- [x] Implement URL extraction from Telegram messages.
- [x] Implement deterministic platform detection.
- [x] Detect Instagram URLs.
- [x] Detect Pinterest URLs.
- [x] Detect Facebook URLs.
- [x] Detect TikTok URLs.
- [x] Detect YouTube URLs.
- [x] Detect X/Twitter URLs.
- [x] Detect Reddit URLs.
- [x] Detect generic URLs.
- [x] Add unit tests for URL extraction.
- [x] Add unit tests for platform detection.
- [x] Add safe unsupported URL errors.

## Phase 3 — Public Download MVP

- [x] Implement downloader adapter contract.
- [x] Implement downloader manager.
- [x] Implement yt-dlp wrapper.
- [x] Implement gallery-dl wrapper.
- [x] Implement public download job model.
- [x] Implement temporary storage layout.
- [x] Implement Telegram sender interface.
- [x] Mock Telegram sender in tests.
- [x] Clean temporary files after successful sends.
- [x] Add integration test for public download job lifecycle.
- [x] Document public download commands and limitations.

## Phase 4 — Async Worker and Persistence

- [x] Implement PostgreSQL models.
- [x] Add database migrations.
- [x] Implement Redis queue integration.
- [x] Implement downloader worker.
- [x] Ensure bot handlers enqueue jobs instead of downloading directly.
- [x] Implement job status updates.
- [x] Implement job history.
- [x] Implement retry policy.
- [x] Add queue-to-worker integration tests.
- [x] Document database and queue commands.

## Phase 5 — Web Session Portal and Vault

- [x] Implement FastAPI web portal.
- [x] Implement one-time connect tokens.
- [x] Bind connect tokens to Telegram user and platform.
- [x] Enforce token expiration.
- [x] Enforce one-time token use.
- [x] Implement session validation.
- [x] Implement encrypted session storage.
- [x] Ensure only session vault can decrypt sessions.
- [x] Implement `/sessions`.
- [x] Implement `/disconnect`.
- [x] Add session ownership tests.
- [x] Add revoked session tests.
- [x] Add expired token tests.
- [x] Add no-plaintext-secret log tests.
- [x] Document session connection and revocation.

## Phase 6 — Authenticated Downloads

- [ ] Use only the requesting user's stored session.
- [ ] Refuse authenticated downloads without a user-owned session.
- [ ] Prevent cross-user session use.
- [ ] Normalize `SESSION_MISSING` errors.
- [ ] Normalize `SESSION_EXPIRED` errors.
- [ ] Normalize `ACCESS_DENIED` errors.
- [ ] Ensure no shared platform account fallback exists.
- [ ] Add authenticated download security tests.
- [ ] Document authenticated download behavior.

## Phase 7 — Multi-Engine Platform Adapters

- [ ] Implement Instagram adapter fallback rules.
- [ ] Implement Pinterest adapter fallback rules.
- [ ] Implement Facebook adapter.
- [ ] Implement TikTok adapter.
- [ ] Implement YouTube adapter.
- [ ] Implement X/Twitter adapter.
- [ ] Implement Reddit adapter.
- [ ] Implement generic adapter.
- [ ] Normalize engine errors.
- [ ] Add adapter selection tests.
- [ ] Add fallback safety tests.

## Phase 8 — Media Processing and Limits

- [ ] Implement FFmpeg compression.
- [ ] Implement thumbnail generation.
- [ ] Implement Telegram media groups.
- [ ] Enforce max file size.
- [ ] Enforce max temporary storage per user.
- [ ] Add oversized media handling.
- [ ] Add configurable quality limits.
- [ ] Add temporary cleanup worker.
- [ ] Add media processing tests.
- [ ] Document media limits.

## Phase 9 — Production Hardening

- [ ] Finalize production Dockerfiles.
- [ ] Finalize production Docker Compose file.
- [ ] Document HTTPS setup.
- [ ] Document Nginx reverse proxy setup.
- [ ] Add container health checks.
- [ ] Add rate limits.
- [ ] Add metrics.
- [ ] Add backup commands.
- [ ] Add restore commands.
- [ ] Add admin maintenance commands.
- [ ] Verify Docker Compose boots all required services.
- [ ] Update production runbook.

## Completion Rules

- Every completed phase has tests added or updated where applicable.
- Every completed phase has README or docs updated where behavior, commands, environment variables, schema, or deployment steps changed.
- Every completed phase has the relevant security checklist reviewed.
- Every completed phase has this roadmap updated before the final report.
