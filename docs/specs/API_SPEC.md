# Internal API Specification

This document defines contracts to implement later. It is not source code.

## Web Portal Routes

### GET /health

Returns service health.

### GET /connect/{platform}?token=...

Validates one-time token and renders session connection page.

### POST /connect/{platform}

Accepts session payload from the user-facing portal, validates it, encrypts it, and stores it.

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
