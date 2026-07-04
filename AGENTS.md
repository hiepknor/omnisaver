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

- Relevant unit tests are added or updated.
- Relevant integration tests are added or updated.
- Security-sensitive paths have explicit tests.
- No plaintext session data appears in logs, errors, traces, fixtures, or job payloads.
- Docker Compose boots all required services when the milestone changes runtime services.
- README and docs are updated with exact commands when behavior, setup, environment variables, schema, or deployment changes.
- The implementation is reviewed against architecture boundaries before commit.

Minimum required tests by area:

- URL detection changes: unit tests for extraction, normalization, and platform detection.
- Downloader selection changes: unit tests for adapter selection, fallback eligibility, and normalized errors.
- Session or auth changes: unit tests for ownership checks, revoked sessions, expired sessions, and cross-user isolation.
- Public job lifecycle changes: integration test with downloader and Telegram sender mocked where external services are not deterministic.
- Configuration changes: tests for defaults, required values, invalid values, and secret redaction.

## Documentation Update Rule

Every implementation change must update the relevant docs if behavior, commands, environment variables, database schema, or deployment steps change.

## Roadmap Tracking Rule

Use `docs/engineering/DEVELOPMENT_ROADMAP.md` as the source of truth for implementation progress.

After completing any phase or milestone:

- Review the relevant roadmap checklist.
- Mark completed items with `[x]`.
- Leave incomplete or deferred items unchecked.
- Add new checklist items if the implementation introduces required follow-up work.
- Do not mark a phase complete until the required quality gates and security checks for that phase have passed.
- Mention the roadmap updates in the completion report.

## Security Review Checklist

For every change touching login/session/download behavior, verify:

- Is the requester the same user who owns the session?
- Is the platform session encrypted at rest?
- Are cookies excluded from logs, errors, traces, and job payloads?
- Can the user revoke their session?
- Are private links handled only when the session is authorized?
- Is rate limiting applied?

## Strict Implementation Workflow

Follow this workflow for every implementation phase or milestone.

### 1. Context Review

Before changing files:

- Read `README.md`.
- Read `docs/architecture/SYSTEM_DESIGN.md`.
- Read `docs/engineering/IMPLEMENTATION_ROADMAP.md`.
- Read `docs/engineering/DEVELOPMENT_ROADMAP.md`.
- Read the relevant product, spec, security, testing, and operations docs for the current milestone.
- Check `git status --short` and identify existing user changes.
- Do not overwrite or revert user changes unless explicitly asked.
- Confirm the milestone scope and avoid unrelated refactors.

### 2. Design Pass

Before implementation:

- Identify the affected architecture boundary.
- Identify the expected contracts, inputs, outputs, and error codes.
- Choose the simplest design that satisfies the current milestone.
- Keep bot, worker, downloader, vault, database, and media processing responsibilities separate.
- Define the tests that will prove the behavior before or alongside the implementation.

### 3. Implementation

While implementing:

- Keep changes small and reviewable.
- Prefer typed, explicit Python modules over framework magic.
- Keep external engine calls behind wrappers.
- Keep Telegram handlers thin.
- Never pass cookies, sessions, access tokens, or secrets through logs or generic job payloads.
- Add comments only for non-obvious decisions or security-sensitive behavior.
- Update docs in the same change when commands, behavior, configuration, schema, or deployment steps change.

### 4. Testing

Before considering work complete:

- Run the targeted tests for the changed area.
- Run the full test suite when the change touches shared contracts, security, downloader behavior, persistence, or runtime configuration.
- Run formatting, linting, and type checks once the project has those tools.
- Run Docker Compose validation when service definitions, Dockerfiles, environment variables, ports, volumes, or startup commands change.
- If a required check cannot run, document the exact reason and do not mark the milestone complete.

### 5. Diff Review

Before committing:

- Review `git diff` completely.
- Verify the diff is limited to the milestone scope.
- Verify generated files, caches, secrets, local indexes, and temporary files are not included.
- Verify docs and roadmap changes match the actual implementation.
- Verify `.env.example` contains placeholders only.
- Verify no private URLs, credentials, cookies, tokens, or session dumps are committed.

### 6. Self Review

Before finalizing:

- Review the change as if reviewing another engineer's pull request.
- Look for incorrect ownership checks, blocking work in handlers, unsafe retries, missing cleanup, weak error mapping, leaky logs, and unclear contracts.
- Check whether tests would fail before the implementation and pass after it.
- Check whether the implementation can be debugged and operated from the documented commands.
- Fix issues found in self-review before commit.

### 7. Roadmap and Commit

After tests and self-review pass:

- Update `docs/engineering/DEVELOPMENT_ROADMAP.md`.
- Mark only completed checklist items with `[x]`.
- Leave incomplete or deferred items unchecked.
- Commit after each completed phase or milestone.
- Include implementation, tests, docs, and roadmap updates in the same milestone commit.
- Use a clear commit message that names the milestone or phase.
- Do not commit if required checks failed, unless the user explicitly asks for a checkpoint commit and the commit message clearly states the incomplete status.
- Push only when the user asks for a push or when the current task explicitly includes pushing.

## Recommended Agent Workflow

1. Read `README.md`.
2. Read `docs/architecture/SYSTEM_DESIGN.md`.
3. Read `docs/engineering/IMPLEMENTATION_ROADMAP.md`.
4. Read `docs/engineering/DEVELOPMENT_ROADMAP.md`.
5. Read all docs relevant to the current milestone.
6. Check `git status --short`.
7. Define the milestone scope and tests.
8. Implement one milestone only.
9. Add or update tests.
10. Run targeted checks and full checks when required.
11. Review `git diff`.
12. Perform self-review.
13. Update docs.
14. Update roadmap checkboxes.
15. Commit the completed milestone.
16. Produce a completion report with tests run, roadmap updates, commit hash, and known limitations.
