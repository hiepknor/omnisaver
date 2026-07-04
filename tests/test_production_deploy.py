import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_production_compose_defines_hardened_services() -> None:
    compose = _read("deploy/docker/docker-compose.production.example.yml")

    for service in ("postgres:", "redis:", "bot:", "web:", "worker:", "cleanup-worker:", "caddy:"):
        assert service in compose
    assert "image: caddy:2.9-alpine" in compose
    assert "./Caddyfile.example:/etc/caddy/Caddyfile:ro" in compose
    assert "caddy_data:" in compose
    assert "restart: unless-stopped" in compose
    assert "healthcheck:" in compose
    assert "condition: service_healthy" in compose
    assert '["CMD", "python", "-m", "omnisaver_bot", "health"]' in compose
    assert "internal: true" in compose
    assert "max-size: \"10m\"" in compose
    assert "ports:" in compose
    assert "443:443" in compose


def test_production_dockerfiles_run_as_non_root_and_worker_installs_ffmpeg() -> None:
    bot = _read("deploy/docker/Dockerfile.bot")
    web = _read("deploy/docker/Dockerfile.web")
    worker = _read("deploy/docker/Dockerfile.worker")

    for dockerfile in (bot, web, worker):
        assert "useradd --system" in dockerfile
        assert "USER omnisaver" in dockerfile
        assert "pip install --no-cache-dir ." in dockerfile

    assert "apt-get install -y --no-install-recommends ffmpeg" in worker


def test_project_dependencies_install_downloader_engine_clis() -> None:
    pyproject = tomllib.loads(_read("pyproject.toml"))
    dependencies = set(pyproject["project"]["dependencies"])

    assert "yt-dlp==2026.6.9" in dependencies
    assert "gallery-dl==1.32.5" in dependencies
    assert "instaloader==4.15.1" in dependencies
    assert "python-telegram-bot==22.8" in dependencies


def test_caddy_config_enforces_https_proxy_and_headers() -> None:
    caddyfile = _read("deploy/docker/Caddyfile.example")

    assert "omnisaver.onio.cc" in caddyfile
    assert "email admin@omnisaver.onio.cc" not in caddyfile
    assert "reverse_proxy web:8000" in caddyfile
    assert "max_size 2MB" in caddyfile
    assert "X-Content-Type-Options nosniff" in caddyfile
    assert "X-Frame-Options DENY" in caddyfile
    assert "Referrer-Policy no-referrer" in caddyfile


def test_admin_scripts_exist_and_are_executable() -> None:
    for script in (
        "deploy/scripts/admin.sh",
        "deploy/scripts/backup_postgres.sh",
        "deploy/scripts/migrate.sh",
        "deploy/scripts/restore_postgres.sh",
        "deploy/scripts/healthcheck.sh",
        "deploy/scripts/metrics.sh",
    ):
        path = ROOT / script
        assert path.exists()
        assert os.access(path, os.X_OK)


def test_admin_scripts_use_expected_compose_commands() -> None:
    admin = _read("deploy/scripts/admin.sh")
    backup = _read("deploy/scripts/backup_postgres.sh")
    migrate = _read("deploy/scripts/migrate.sh")
    restore = _read("deploy/scripts/restore_postgres.sh")
    metrics = _read("deploy/scripts/metrics.sh")

    assert "backup|migrate|restore <file>|cleanup|health|metrics|logs" in admin
    assert "exec deploy/scripts/migrate.sh" in admin
    assert "pg_dump" in backup
    assert "gzip" in backup
    assert "packages/db/migrations/001_initial.sql" in migrate
    assert "psql" in migrate
    assert "psql" in restore
    assert "redis-cli llen" in metrics
    assert "docker stats --no-stream" in metrics
