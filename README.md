# OmniSaver

OmniSaver is a Telegram bot platform for downloading media from public links and user-authorized private links.

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

Current status: **planning scaffold complete**.

The next milestone is `Phase 1 — Repository Foundation` in `docs/engineering/DEVELOPMENT_ROADMAP.md`.

## Core Documents

- `AGENTS.md` — instructions for Codex/AI coding agents.
- `docs/product/PRODUCT_REQUIREMENTS.md` — product scope and behavior.
- `docs/architecture/SYSTEM_DESIGN.md` — system architecture.
- `docs/specs/FUNCTIONAL_SPEC.md` — feature-level requirements.
- `docs/specs/API_SPEC.md` — internal API contracts to implement later.
- `docs/security/SECURITY_MODEL.md` — session vault, cookies, privacy and abuse rules.
- `docs/engineering/IMPLEMENTATION_ROADMAP.md` — phased implementation plan.
- `docs/engineering/DEVELOPMENT_ROADMAP.md` — implementation checklist and progress tracker.
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

Build only Phase 1 — Repository Foundation:

1. Create the Python 3.11 project structure.
2. Add test, lint, type-check, and config-loading foundations.
3. Add Docker build and local Compose skeletons.
4. Update README with exact setup, test, and run commands.
5. Do not add downloader logic yet.
