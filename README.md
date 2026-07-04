# OmniSaver

Documentation-only scaffold for OmniSaver, a Telegram bot platform that downloads media from public links and from user-authorized private/session-based links.

This repository intentionally contains **no application source code**. It is designed to be handed to an AI coding agent such as Codex for implementation.

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

Current status: **planning scaffold only**.

Do not add production code until the implementation plan in `docs/engineering/IMPLEMENTATION_ROADMAP.md` is accepted.

## Core Documents

- `AGENTS.md` — instructions for Codex/AI coding agents.
- `docs/product/PRODUCT_REQUIREMENTS.md` — product scope and behavior.
- `docs/architecture/SYSTEM_DESIGN.md` — system architecture.
- `docs/specs/FUNCTIONAL_SPEC.md` — feature-level requirements.
- `docs/specs/API_SPEC.md` — internal API contracts to implement later.
- `docs/security/SECURITY_MODEL.md` — session vault, cookies, privacy and abuse rules.
- `docs/engineering/IMPLEMENTATION_ROADMAP.md` — phased implementation plan.
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
│  ├─ bot/                 # Telegram bot service, to be implemented later
│  └─ web/                 # Web session portal, to be implemented later
├─ workers/
│  └─ downloader/          # Download workers, to be implemented later
├─ packages/
│  ├─ downloader/          # Platform adapters, to be implemented later
│  ├─ session-vault/       # Encryption/decryption, to be implemented later
│  ├─ db/                  # Database access, to be implemented later
│  └─ media-processor/     # FFmpeg helpers, to be implemented later
├─ deploy/
│  └─ docker/              # Production deployment templates and docs
├─ docs/
└─ storage/
```

## Recommended First Milestone

Build only Phase 1:

1. Telegram bot receives URL.
2. URL detector identifies platform.
3. Worker downloads public media using yt-dlp/gallery-dl.
4. Bot sends media back to user.
5. Temporary files are cleaned up.
