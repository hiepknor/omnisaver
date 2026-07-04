# Telegram Command Specification

## /start

Response:

```text
Send me a public media link and I will try to download it.
Use /help for supported platforms.
Use /connect_instagram to connect your own session for links that require login.
```

## /help

Must include:

- Supported platforms.
- Public vs authenticated explanation.
- Privacy rule: no bypass.
- Session management commands.

## /connect_instagram

Creates connect token and returns web portal URL.

## /connect_pinterest

Creates connect token and returns web portal URL.

## /connect_facebook

Creates connect token and returns web portal URL.

## /sessions

Shows connected sessions:

```text
Instagram: connected, last checked 2026-07-04
Pinterest: not connected
Facebook: expired
```

## /disconnect

Interactive platform selection or argument-based:

```text
/disconnect instagram
```

## /history

Shows recent jobs:

```text
1. Instagram Reel - completed
2. Pinterest Pin - failed: login required
```
