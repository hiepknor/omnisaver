# Engine Selection

## Principle

Use the most reliable engine per platform, but keep a common adapter contract so engines can be replaced without changing bot logic.

## Engine Matrix

| Platform | Primary | Secondary | Notes |
|---|---|---|---|
| Instagram | gallery-dl | Instaloader, yt-dlp | Best handled with platform-specific support and authenticated sessions. |
| Pinterest | gallery-dl | yt-dlp | gallery-dl is preferred for image/gallery sites. |
| Facebook | yt-dlp | none initially | Most maintained practical option. |
| TikTok | yt-dlp | none initially | Good extractor coverage. |
| YouTube | yt-dlp | none initially | Best-in-class. |
| X/Twitter | yt-dlp | gallery-dl | Both can be useful. |
| Reddit | gallery-dl | yt-dlp | Depends on content type. |
| Generic URL | yt-dlp | none initially | Broad extractor support. |

## Adapter Contract

Every adapter should return a normalized result:

```text
MediaResult
  platform
  source_url
  title
  caption
  media_files[]
  metadata
```

## Fallback Rules

- Fallback only after a known safe failure.
- Retryability and fallback eligibility are separate. Worker retries use `retryable`; engine fallback uses `fallback_allowed`.
- Do not fallback from user-authorized session to a global/shared account.
- Do not retry aggressively against rate limits.
- Preserve safe error codes.

## Engine Invocation

Engines should be called through wrappers, not directly from bot handlers.

Wrappers should:

- Pass output directory by job id.
- Enforce max file size if supported.
- Use cookie/session files only from Session Vault.
- Materialize authenticated cookies only as per-job temporary files with restrictive permissions.
- Pass cookie files through engine flags such as `yt-dlp --cookies`, `gallery-dl --cookies`,
  and `instaloader --cookiefile`.
- Delete temporary cookie files immediately after engine execution.
- Redact command logs.
- Parse output into MediaResult.
