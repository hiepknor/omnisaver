# Telegram Command Specification

## /start

Response must be Vietnamese and Telegram HTML formatted. It should introduce OmniSaver, explain that users can send a public media link, mention session connection for login-required content, and point to `/help`.

Use restrained visual markers such as status emoji, bold labels, and code-formatted command names.

## /help

Must include:

- Supported platforms.
- Public vs authenticated explanation.
- Privacy rule: no bypass.
- Session management commands.
- Vietnamese copy and Telegram HTML formatting.

## /connect_instagram

Creates connect token and returns web portal URL.

## /connect_pinterest

Creates connect token and returns web portal URL.

## /connect_facebook

Creates connect token and returns web portal URL.

## /sessions

Shows connected sessions:

```html
✅ <b>Instagram</b>: đã kết nối · kiểm tra lần cuối 2026-07-04
- <b>Pinterest</b>: chưa kết nối
⚠️ <b>Facebook</b>: đã hết hạn
```

## /disconnect

Interactive platform selection or argument-based:

```text
/disconnect instagram
```

## /history

Shows recent jobs:

```html
1. ✅ <b>Instagram</b> · Hoàn tất · <code>job-id</code>
2. ⚠️ <b>Pinterest</b> · Thất bại · <code>job-id</code>
```

## Plain URL Message

When a supported URL is received, the bot must immediately reply in Vietnamese with:

- queued status;
- detected platform;
- short job id in `<code>`;
- a short note that media will be sent to the same chat when complete.

## Worker Failure Notification

When a worker exhausts retries and marks a job failed, it must send one final Vietnamese HTML notification to the requesting chat with:

- failed status;
- platform;
- short job id;
- safe user-facing reason;
- reconnect command when the failure is session-related.
