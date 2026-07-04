import base64

import pytest
from fastapi.testclient import TestClient

from omnisaver_db import InMemorySessionRepository
from omnisaver_downloader import DownloadError, ErrorCode, Platform
from omnisaver_session_vault import SessionVault
from omnisaver_web import BasicSessionValidator, PortalDependencies, create_app
from omnisaver_worker import VaultSessionResolver


def test_web_portal_session_is_available_to_worker_session_resolver() -> None:
    repository = InMemorySessionRepository()
    vault = SessionVault.from_base64_key(
        base64.b64encode(b"5" * 32).decode("ascii"),
        key_id="key-1",
    )
    app = create_app(
        PortalDependencies(
            repository=repository,
            vault=vault,
            validator=BasicSessionValidator(),
        )
    )
    token, _record = repository.create_connect_token(
        telegram_user_id=123,
        platform=Platform.INSTAGRAM.value,
        ttl_seconds=600,
    )

    response = TestClient(app).post(
        "/connect/instagram",
        json={"token": token, "session_payload": '{"session":"sensitive-marker"}'},
    )

    assert response.status_code == 200
    resolver = VaultSessionResolver(repository=repository, vault=vault)
    session = resolver.resolve(telegram_user_id=123, platform=Platform.INSTAGRAM)

    assert session.platform is Platform.INSTAGRAM
    assert session.payload == b'{"session":"sensitive-marker"}'
    assert "sensitive-marker" not in repr(session)

    stored = repository.get_session(telegram_user_id=123, platform=Platform.INSTAGRAM.value)
    assert stored is not None
    assert b"sensitive-marker" not in stored.encrypted_session

    with pytest.raises(DownloadError) as exc_info:
        resolver.resolve(telegram_user_id=456, platform=Platform.INSTAGRAM)

    assert exc_info.value.code is ErrorCode.SESSION_MISSING
