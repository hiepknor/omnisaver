# AGENTS.md

This repository is intended to be developed by Codex or another AI coding agent.

## Prime Directive

Implement the system incrementally according to the docs. Do not introduce behavior that bypasses platform privacy controls or accesses private content without a valid user-authorized session.

## Hard Constraints

- Do not create application code until the current task explicitly asks for implementation.
- Do not store cookies, sessions, access tokens, or secrets in plaintext.
- Do not log sensitive session data.
- Do not use a shared Instagram/Facebook/Pinterest account to access private content for all users.
- Do not use one user's session to download content for another user.
- Do not implement private-content bypass, exploit-based access, or anti-auth circumvention.
- All authenticated downloads must use the requesting user's own authorized session.
- Keep implementation testable and modular.

## Architecture Rules

Use these boundaries:

```text
apps/bot            Telegram interface only
apps/web            User session connection portal only
workers/downloader  Async job execution only
packages/downloader Platform adapters and engine wrappers
packages/session-vault Encryption and secret handling
packages/db         Persistence layer
packages/media-processor FFmpeg and media normalization
```

The bot must not directly download large media in the request handler. It should enqueue a job and return status updates.

The downloader worker must not directly know Telegram command logic. It should operate on jobs and return normalized results.

The session vault must be the only module allowed to decrypt stored sessions.

## Implementation Style

Preferred stack:

- Python 3.11+
- python-telegram-bot
- FastAPI
- PostgreSQL
- Redis Queue, RQ, or Celery
- yt-dlp
- gallery-dl
- Instaloader
- FFmpeg
- Docker Compose

Keep code typed, small, and explicit. Prefer simple modules over frameworks hidden behind magic.

## Required Quality Gates

Before marking any milestone complete:

- Unit tests for URL detection.
- Unit tests for platform adapter selection.
- Unit tests for session ownership checks.
- Integration test for public download job lifecycle.
- No plaintext session data in logs.
- Docker Compose boots all required services.
- README updated with exact commands.

## Documentation Update Rule

Every implementation change must update the relevant docs if behavior, commands, environment variables, database schema, or deployment steps change.

## Security Review Checklist

For every change touching login/session/download behavior, verify:

- Is the requester the same user who owns the session?
- Is the platform session encrypted at rest?
- Are cookies excluded from logs, errors, traces, and job payloads?
- Can the user revoke their session?
- Are private links handled only when the session is authorized?
- Is rate limiting applied?

## Recommended Agent Workflow

1. Read `README.md`.
2. Read `docs/architecture/SYSTEM_DESIGN.md`.
3. Read `docs/engineering/IMPLEMENTATION_ROADMAP.md`.
4. Implement one milestone only.
5. Add tests.
6. Run all checks.
7. Update docs.
8. Produce a completion report.

