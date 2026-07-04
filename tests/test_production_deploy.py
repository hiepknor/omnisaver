import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_production_compose_defines_hardened_services() -> None:
    compose = _read("deploy/docker/docker-compose.production.example.yml")

    for service in ("postgres:", "redis:", "bot:", "web:", "worker:", "cleanup-worker:", "nginx:"):
        assert service in compose
    assert "restart: unless-stopped" in compose
    assert "healthcheck:" in compose
    assert "condition: service_healthy" in compose
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


def test_nginx_config_enforces_https_proxy_and_rate_limits() -> None:
    nginx = _read("deploy/docker/nginx.example.conf")

    assert "limit_req_zone" in nginx
    assert "limit_conn_zone" in nginx
    assert "return 301 https://$host$request_uri;" in nginx
    assert "listen 443 ssl http2;" in nginx
    assert "proxy_pass http://omnisaver_web" in nginx
    assert "X-Forwarded-Proto https" in nginx


def test_admin_scripts_exist_and_are_executable() -> None:
    for script in (
        "deploy/scripts/admin.sh",
        "deploy/scripts/backup_postgres.sh",
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
    restore = _read("deploy/scripts/restore_postgres.sh")
    metrics = _read("deploy/scripts/metrics.sh")

    assert "backup|restore <file>|cleanup|health|metrics|logs" in admin
    assert "pg_dump" in backup
    assert "gzip" in backup
    assert "psql" in restore
    assert "redis-cli llen" in metrics
    assert "docker stats --no-stream" in metrics
