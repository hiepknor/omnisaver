# System Design

## Overview

The system is composed of a Telegram bot, a web session portal, an async download worker, a session vault, PostgreSQL, Redis, and temporary object/file storage.

```text
Telegram User
  |
  v
Telegram Bot Service
  |
  +--> URL Detector
  +--> Job Creator
  +--> Status Messenger
  |
  v
Redis Queue
  |
  v
Download Worker
  |
  +--> Downloader Manager
  |     +--> Instagram Adapter
  |     +--> Pinterest Adapter
  |     +--> Facebook Adapter
  |     +--> Generic Adapter
  |
  +--> Session Vault
  +--> Media Processor
  +--> Telegram Sender
  |
  v
PostgreSQL + Temporary Storage
```

## Components

### Bot Service

Responsibilities:

- Handle `/start`, `/help`, `/connect_*`, `/disconnect`, `/sessions`.
- Parse user messages for URLs.
- Create download jobs.
- Send job status updates.
- Send final media result or error message.

The bot should not run long downloads inside the Telegram update handler.

### Web Session Portal

Responsibilities:

- Accept one-time connection tokens from the bot.
- Let users connect platform sessions.
- Validate sessions.
- Store encrypted session payloads through Session Vault.
- Allow session revocation.

### Download Worker

Responsibilities:

- Pull jobs from Redis.
- Resolve platform adapter.
- Load user session only if required and owned by the requesting user.
- Download media.
- Normalize result.
- Send media to Telegram.
- Mark job complete or failed.

### Downloader Manager

Provides one stable interface:

```text
download(url, user_context) -> MediaResult
```

It chooses the platform adapter and fallback engine.

### Session Vault

Responsibilities:

- Encrypt session data at rest.
- Decrypt session data only inside authorized worker flow.
- Hide secrets from logs and errors.
- Support revocation and key rotation.

### Media Processor

Responsibilities:

- Validate downloaded files.
- Check file size.
- Compress video when needed.
- Generate thumbnails where useful.
- Prepare Telegram media groups.

## Data Flow: Public Download

```text
1. User sends URL.
2. Bot detects platform.
3. Bot creates job.
4. Worker downloads using public engine.
5. Worker processes media.
6. Bot/worker sends files back.
7. Temporary files are cleaned.
```

## Data Flow: Authorized Download

```text
1. User runs /connect_instagram.
2. Bot creates one-time token.
3. User opens HTTPS portal.
4. User provides/establishes an authorized session.
5. Portal validates session.
6. Vault encrypts session.
7. User sends private URL.
8. Worker decrypts only that user's session.
9. Engine downloads content if the session is authorized.
10. Media is sent back.
```

## Failure Model

Common failure types:

- Unsupported URL.
- Login required.
- Session expired.
- Access denied.
- Media too large.
- Engine extraction failed.
- Platform rate limit.
- Telegram upload failed.
- Temporary storage full.

All failures should map to safe user-facing messages without leaking internal stack traces or cookies.
