# Security Model

## Security Goals

- Protect user sessions and cookies.
- Prevent cross-user session use.
- Avoid private-content bypass behavior.
- Minimize sensitive data exposure.
- Make abuse harder through rate limits and quotas.

## Authorization Principle

Authenticated downloads are allowed only when:

1. The Telegram user owns the stored platform session.
2. The session is valid.
3. The platform allows that session to view the content.

The system must not attempt to bypass access restrictions.

## Session Storage

Sessions must be encrypted before being written to the database.

Recommended encryption:

- AES-256-GCM with a server-side master key.
- Or libsodium secretbox/sealed box.

Required metadata:

- platform
- owner user id
- key id
- created_at
- updated_at
- expires_at if known
- last_validated_at
- status

## Plaintext Prohibition

Never store these in plaintext:

- Cookies
- Session IDs
- Access tokens
- Refresh tokens
- Authorization headers
- Browser storage dumps

Never log these values.

## Tokenized Connect Flow

Connection tokens must be:

- One-time use.
- Bound to Telegram user id.
- Bound to platform.
- Short lived, default 10 minutes.
- Random and high entropy.

## Session Validation

After session submission, the portal should perform a safe validation request to confirm that the session works.

Do not download private media during validation. Only confirm account/session identity and accessibility status.

## Revocation

Users must be able to revoke sessions via `/disconnect`.

Revocation should:

- Mark the DB session as revoked.
- Delete encrypted payload where practical.
- Prevent future jobs from using the session.

## Rate Limiting

Minimum limits:

- Per-user messages per minute.
- Per-user downloads per hour.
- Max concurrent jobs per user.
- Max file size per job.
- Max total temporary storage per user.

## Abuse Cases

The system should refuse or limit:

- Mass scraping.
- Batch downloading entire private profiles.
- Repeated failed access attempts.
- Links known to be malicious.
- Extremely large downloads.

## Safe User Messages

Do not expose internal errors. Use messages like:

- This link requires login. Connect your account first.
- Your session expired. Please reconnect.
- Your account does not have permission to view this content.
- This file is too large to send through Telegram.
