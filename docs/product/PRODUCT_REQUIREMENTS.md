# Product Requirements

## Product Name

OmniSaver

## Vision

OmniSaver is a Telegram bot that lets users send media URLs and receive downloadable photos/videos back in Telegram, with support for public links and user-authorized private/session-based links.

## User Stories

### Public Download

As a Telegram user, I send a public Instagram/Pinterest/Facebook/TikTok/YouTube link and receive the media file back.

### Authorized Private Download

As a Telegram user, I connect my own platform session and download content that my own account is allowed to view.

### Session Management

As a Telegram user, I can view connected platforms and disconnect them at any time.

### Failure Transparency

As a Telegram user, I receive a clear error when a link is unsupported, private without authorization, too large, deleted, or rate-limited.

## MVP Scope

- Telegram bot receives URLs.
- Basic URL detection.
- Public downloads through yt-dlp and gallery-dl.
- Send media back to Telegram.
- Job status messages.
- Temporary storage cleanup.

## V2 Scope

- Redis queue.
- PostgreSQL job history.
- Web portal for session connection.
- Session vault encryption.
- Instagram/Pinterest/Facebook authenticated download when authorized.

## V3 Scope

- Multi-engine fallback.
- FFmpeg compression.
- Admin dashboard.
- Metrics and alerting.
- Per-user quotas.

## Out of Scope

- Private content bypass.
- Exploiting platform bugs.
- Selling user session access.
- Browser fingerprint evasion arms race.
- Full social media archiving service.
