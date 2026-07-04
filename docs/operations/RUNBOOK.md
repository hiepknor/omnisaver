# Operations Runbook

## Common Commands

### View logs

```bash
deploy/scripts/admin.sh logs
```

### Restart worker

```bash
docker compose -f deploy/docker/docker-compose.production.yml restart worker
```

### Restart bot

```bash
docker compose -f deploy/docker/docker-compose.production.yml restart bot
```

### Check disk usage

```bash
du -sh storage/downloads
```

### Check service health

```bash
deploy/scripts/admin.sh health
```

### Check basic metrics

```bash
deploy/scripts/admin.sh metrics
```

### Back up PostgreSQL

```bash
deploy/scripts/admin.sh backup
```

### Restore PostgreSQL

```bash
deploy/scripts/admin.sh restore backups/postgres/omnisaver-YYYYMMDDTHHMMSSZ.sql.gz
```

### Clean temporary files manually

```bash
deploy/scripts/admin.sh cleanup
```

## Incident: Disk Full

1. Stop workers.
2. Run `deploy/scripts/admin.sh cleanup`.
3. Check failed cleanup worker logs.
4. Restart workers.
5. Add disk alert.

## Incident: Platform Download Failing

1. Check whether all platforms fail or only one.
2. Update yt-dlp/gallery-dl/Instaloader image/package.
3. Test with public sample URL.
4. Check platform rate limits.
5. Return safe temporary failure message to users.

## Incident: Session Leak Suspected

1. Stop web and worker services.
2. Rotate session vault master key if possible.
3. Revoke all sessions.
4. Review logs for secret exposure.
5. Force users to reconnect.

## Incident: Telegram Upload Failing

1. Check Telegram Bot API status.
2. Check file size.
3. Try sending as document.
4. Enable compression if available.

## Incident: Backup Failing

1. Run `deploy/scripts/admin.sh health`.
2. Check `backups/postgres` free disk space.
3. Run `deploy/scripts/admin.sh backup` manually.
4. Verify the generated `.sql.gz` can be listed and copied off-host.
