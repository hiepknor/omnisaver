import base64

from fastapi.testclient import TestClient
from pytest import LogCaptureFixture

from omnisaver_db import InMemorySessionRepository, SessionStatus
from omnisaver_session_vault import EncryptedSession, SessionVault, session_associated_data
from omnisaver_web import BasicSessionValidator, PortalDependencies, create_app


def _client() -> tuple[TestClient, InMemorySessionRepository, SessionVault]:
    repository = InMemorySessionRepository()
    vault = SessionVault.from_base64_key(
        base64.b64encode(b"3" * 32).decode("ascii"),
        key_id="key-1",
    )
    app = create_app(
        PortalDependencies(
            repository=repository,
            vault=vault,
            validator=BasicSessionValidator(),
        )
    )
    return TestClient(app), repository, vault


def test_connect_flow_encrypts_session_and_marks_token_used() -> None:
    client, repository, vault = _client()
    token, token_record = repository.create_connect_token(
        telegram_user_id=123,
        platform="instagram",
        ttl_seconds=600,
    )

    get_response = client.get(f"/connect/instagram?token={token}")
    assert get_response.status_code == 200
    assert get_response.json()["telegram_user_id"] == 123

    post_response = client.post(
        "/connect/instagram",
        json={"token": token, "session_payload": '{"cookie":"secret-cookie"}'},
    )

    assert post_response.status_code == 200
    assert post_response.json() == {"platform": "instagram", "status": "connected"}
    assert repository.get_valid_connect_token(token=token, platform="instagram") is None

    session = repository.get_session(telegram_user_id=123, platform="instagram")
    assert session is not None
    assert session.status is SessionStatus.CONNECTED
    assert b"secret-cookie" not in session.encrypted_session
    assert (
        vault.decrypt(
            EncryptedSession(key_id=session.encryption_key_id, payload=session.encrypted_session),
            associated_data=session_associated_data(
                user_id=str(token_record.user_id),
                platform="instagram",
            ),
        )
        == b'{"cookie":"secret-cookie"}'
    )


def test_connect_does_not_log_plaintext_session(caplog: LogCaptureFixture) -> None:
    client, repository, _vault = _client()
    token, _record = repository.create_connect_token(
        telegram_user_id=123,
        platform="instagram",
        ttl_seconds=600,
    )

    with caplog.at_level("INFO"):
        response = client.post(
            "/connect/instagram",
            json={"token": token, "session_payload": '{"cookie":"secret-cookie"}'},
        )

    assert response.status_code == 200
    assert "secret-cookie" not in caplog.text


def test_connect_rejects_reused_token() -> None:
    client, repository, _vault = _client()
    token, _record = repository.create_connect_token(
        telegram_user_id=123,
        platform="instagram",
        ttl_seconds=600,
    )
    response = client.post(
        "/connect/instagram",
        json={"token": token, "session_payload": "payload"},
    )
    assert response.status_code == 200

    reused = client.post(
        "/connect/instagram",
        json={"token": token, "session_payload": "payload"},
    )
    assert reused.status_code == 404


def test_connect_rejects_unsupported_platform_without_storing_session() -> None:
    client, repository, _vault = _client()
    token, _record = repository.create_connect_token(
        telegram_user_id=123,
        platform="youtube",
        ttl_seconds=600,
    )

    response = client.post(
        "/connect/youtube",
        json={"token": token, "session_payload": "payload"},
    )

    assert response.status_code == 400
    assert repository.list_sessions(telegram_user_id=123) == []


def test_disconnect_revokes_session() -> None:
    client, repository, _vault = _client()
    repository.store_encrypted_session(
        telegram_user_id=123,
        platform="instagram",
        encrypted_session=b"encrypted",
        encryption_key_id="key-1",
    )

    response = client.post("/disconnect/instagram", json={"telegram_user_id": 123})

    assert response.status_code == 200
    session = repository.get_session(telegram_user_id=123, platform="instagram")
    assert session is not None
    assert session.status is SessionStatus.REVOKED
    assert session.encrypted_session == b""
