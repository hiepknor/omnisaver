# OmniSaver UX Upgrade Plan

This document turns the July 4, 2026 UX audit into an implementation plan. It focuses on the user-facing Telegram bot, group usage, web session portal, download status feedback, and documentation consistency.

## UX Principles

- Keep every user-facing bot response in Vietnamese.
- Make privacy boundaries clear without exposing session, token, cookie, or account details.
- Keep group chats quiet by default; respond only to commands or mentioned URL requests.
- Make private-link recovery actionable: users should know exactly what to do next.
- Prefer explicit status, buttons, and short messages over long explanations.
- Do not weaken session ownership or platform access rules for convenience.

## Phase 11A - Web Session Portal UX

Goal: turn the current JSON-only session portal into a usable mobile-first connection flow.

- [x] Render an HTML page for `GET /connect/{platform}?token=...`.
- [x] Add Vietnamese invalid-token, expired-token, used-token, and success states.
- [x] Add a guided form for submitting the session payload.
- [x] Show platform-specific guidance for Instagram, Pinterest, and Facebook.
- [x] Add official platform login links and warn users not to enter passwords in OmniSaver.
- [x] Validate Instagram session input as Netscape `cookies.txt` with required cookies.
- [x] Add clear warnings that users must only connect their own authorized session.
- [x] Keep session payloads out of logs, traces, URLs, and client-side storage.
- [x] Add tests for rendered portal states and successful submission.
- [x] Update `docs/specs/API_SPEC.md` to match the implemented portal contract.

Acceptance criteria:

- A normal Telegram user can open the bot-provided link and complete connection without using raw API tools.
- Invalid or expired links show a human-readable Vietnamese page.
- The portal still stores sessions encrypted at rest and does not log plaintext session data.

## Phase 11B - Telegram Group Onboarding

Goal: make group usage predictable while keeping the bot quiet.

- [ ] Update `/help` to explain that group URL messages must mention the bot username.
- [ ] Add a concise group-specific help response when `/help` is used in a group.
- [ ] Document examples such as `@bot_username https://example.com/video`.
- [ ] Add configuration or startup validation for the expected bot username if needed.
- [ ] Keep non-mentioned group URL messages silently ignored.
- [ ] Add tests for private help vs group help copy.

Acceptance criteria:

- Users understand why a plain group URL gets no response.
- Account and session commands still require private chat.
- Group replies do not reveal session status, connect tokens, or history.

## Phase 11C - Private-Link Recovery UX

Goal: reduce manual work when a private link fails because a user has no valid session.

- [x] Pass encrypted user cookies to downloader engines through per-job temporary cookie files.
- [ ] Add Telegram inline buttons for session-related failures where supported.
- [ ] Add a button or deep link to open private chat with the bot.
- [ ] Include the relevant `/connect_<platform>` command in the recovery message.
- [ ] Preserve the privacy rule: users must reconnect in private chat.
- [ ] Consider a safe retry flow after session connection without putting cookies or tokens in job payloads.
- [ ] Add tests for session-missing, session-expired, and login-required recovery messages.

Acceptance criteria:

- A user who posts a private link in a group gets a clear, actionable recovery path.
- Recovery does not create connect tokens in group chats.
- No user's session is used for another user's job.

## Phase 11D - Job Status and Progress UX

Goal: make long-running jobs feel reliable without spamming chats.

- [ ] Add `/status <job_id>` in private chat.
- [ ] Decide whether group `/status` is allowed for jobs delivered to that group.
- [ ] Show queued, started, retrying, completed, and failed states in Vietnamese.
- [ ] Add retry count or short wait guidance for retryable failures.
- [ ] Keep queued messages short and include the short job id.
- [ ] Add tests for status lookup ownership and safe not-found responses.

Acceptance criteria:

- Users can check a job without resending the same URL.
- Status lookup does not expose another user's private job details.
- Worker retry behavior is visible enough to reduce confusion.

## Phase 11E - Media Delivery Polish

Goal: improve how multi-file posts and albums arrive in Telegram.

- [ ] Implement Telegram `sendMediaGroup` for eligible photo/video albums.
- [ ] Fall back to individual sends when media groups are not supported for the result.
- [ ] Keep captions readable and avoid duplicating long captions across every file.
- [ ] Add tests for media group payload construction.
- [ ] Update roadmap/docs if any current media-group checkbox is only metadata support.

Acceptance criteria:

- Carousel-style results arrive as a coherent Telegram album when possible.
- Single-media results keep the existing photo/video/document behavior.
- Oversized files still fail with safe Vietnamese errors.

## Phase 11F - Error and History Polish

Goal: keep all visible failures understandable and localized.

- [ ] Map stored error codes to Vietnamese messages when rendering `/history`.
- [ ] Avoid rendering raw engine messages directly to users.
- [ ] Add safe fallback copy for old jobs that contain English or technical errors.
- [ ] Update service-backed E2E tests to match current Vietnamese HTML copy.
- [ ] Ensure test doubles accept Telegram reply options such as `parse_mode`.

Acceptance criteria:

- `/history` never shows cookies, tokens, stack traces, or raw session payloads.
- Existing skipped E2E tests can run against the current UX contract.
- Old job records degrade gracefully with safe Vietnamese fallback copy.

## Suggested Implementation Order

1. Phase 11A: Web Session Portal UX.
2. Phase 11B: Telegram Group Onboarding.
3. Phase 11C: Private-Link Recovery UX.
4. Phase 11D: Job Status and Progress UX.
5. Phase 11E: Media Delivery Polish.
6. Phase 11F: Error and History Polish.

## Required Quality Gates

- Update relevant unit or integration tests for every changed user-facing flow.
- Run targeted tests for the changed boundary.
- Run the full test suite when shared bot, worker, database, or session contracts change.
- Review `git diff` before commit.
- Perform self-review for privacy, session ownership, logging, and group-chat leakage.
- Update this document and `docs/engineering/DEVELOPMENT_ROADMAP.md` after each completed UX phase.
