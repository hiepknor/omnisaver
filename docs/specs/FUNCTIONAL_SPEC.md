# Functional Specification

## Commands

### /start

Shows welcome text and supported platforms.

### /help

Shows usage examples and privacy rules.

### /connect_instagram

Creates a one-time link to the web portal for Instagram session connection.

### /connect_pinterest

Creates a one-time link to the web portal for Pinterest session connection.

### /connect_facebook

Creates a one-time link to the web portal for Facebook session connection.

### /sessions

Lists connected platforms and session status.

### /disconnect

Lets the user revoke one platform session.

### /history

Shows recent download jobs.

## URL Handling

The bot should accept messages containing one or more URLs.

For MVP, process one URL per message. Later versions can support batches.

## Platform Detection

Detection should be deterministic and covered by tests.

Examples:

- instagram.com/p/*
- instagram.com/reel/*
- instagram.com/stories/*
- pinterest.com/pin/*
- pin.it/*
- facebook.com/*/videos/*
- facebook.com/reel/*
- tiktok.com/@*/video/*
- youtube.com/watch?v=*
- youtu.be/*

## Download Behavior

### Public Links

Try public extraction first. If login is required, return a message suggesting `/connect_<platform>`.

### Authenticated Links

Use the requesting user's own encrypted session. If no session exists, do not use a global fallback account.

If a public attempt reports login required, the worker may retry with only that requesting user's stored session. Missing, revoked, expired, or unauthorized sessions must return safe errors.

## Telegram Sending

- Send images as photos when possible.
- Send videos as videos when within Telegram limits.
- Send oversized or unusual formats as documents if allowed.
- For carousels, use media groups when possible.
- Generate video thumbnails when possible.
- Compress oversized videos before rejecting them.
- Reject oversized non-video files safely.

## Cleanup

- Temporary files must be deleted after successful send.
- Failed jobs should be cleaned by a scheduled cleanup worker.
- Configurable TTL: default 24 hours.
- Temporary storage is tracked per Telegram user.
