# Internal API Specification

This document defines contracts to implement later. It is not source code.

## Web Portal Routes

### GET /health

Returns service health.

### GET /connect/{platform}?token=...

Validates one-time token and renders a Vietnamese, mobile-first session connection page.

When the token is invalid, expired, already used, or bound to another platform, the route returns an HTML error page with HTTP 404.

The connection page may link users to the official platform login page, but OmniSaver must not render a platform password form or collect platform passwords.

### POST /connect/{platform}

Accepts session payload from the user-facing portal, validates it, encrypts it, and stores it.

Supported request formats:

- Browser form submit with `application/x-www-form-urlencoded`.
- Internal/API JSON body:

```json
{
  "token": "one-time-token",
  "session_payload": "platform session payload"
}
```

Browser form responses render HTML success or validation pages. JSON requests keep the internal API response:

```json
{
  "platform": "instagram",
  "status": "connected"
}
```

Plaintext session payloads must not appear in logs, URLs, traces, or job payloads.

### POST /disconnect/{platform}

Revokes stored session for the authenticated Telegram user token.

## Internal Job Model

```json
{
  "job_id": "uuid",
  "telegram_user_id": 123456,
  "chat_id": 123456,
  "platform": "instagram",
  "url": "https://example.com/...",
  "requires_auth": false,
  "status": "queued"
}
```

`requires_auth` is not a session payload. Workers must resolve and decrypt the requesting user's stored platform session at execution time.

## MediaResult Contract

```json
{
  "platform": "instagram",
  "title": "string",
  "caption": "string",
  "media": [
    {
      "type": "photo|video|document",
      "path": "/storage/downloads/job/file.mp4",
      "thumbnail_path": "/storage/downloads/job/file.jpg",
      "mime_type": "video/mp4",
      "size_bytes": 123456
    }
  ],
  "metadata": {}
}
```

## Error Contract

```json
{
  "code": "SESSION_EXPIRED",
  "safe_message": "Your Instagram session has expired. Please reconnect with /connect_instagram.",
  "retryable": false
}
```

## Error Codes

- UNSUPPORTED_URL
- LOGIN_REQUIRED
- SESSION_MISSING
- SESSION_EXPIRED
- ACCESS_DENIED
- RATE_LIMITED
- MEDIA_TOO_LARGE
- DOWNLOAD_FAILED
- TELEGRAM_UPLOAD_FAILED
- INTERNAL_ERROR
