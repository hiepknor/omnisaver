# Testing Strategy

## Unit Tests

- URL detection.
- Platform mapping.
- Adapter selection.
- Error normalization.
- Session ownership checks.
- Config loading.

## Integration Tests

- Public download job lifecycle.
- Queue to worker flow.
- Temporary file cleanup.
- Telegram sender mocked.
- Session vault encrypt/decrypt.

## Security Tests

- User A cannot use User B session.
- Revoked session cannot be used.
- Expired connect token cannot be used.
- Used connect token cannot be reused.
- Logs do not include cookies.

## Manual Tests

- Instagram public post.
- Instagram public reel.
- Pinterest pin.
- Facebook public video.
- TikTok public video.
- YouTube video.
- Auth-required link with valid user session.
- Auth-required link without valid user session.
