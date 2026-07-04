import base64

import pytest
from cryptography.exceptions import InvalidTag

from omnisaver_session_vault import EncryptedSession, SessionVault, session_associated_data


def test_session_vault_encrypts_and_decrypts_with_associated_data() -> None:
    vault = SessionVault.from_base64_key(
        base64.b64encode(b"0" * 32).decode("ascii"),
        key_id="test-key",
    )
    plaintext = b'{"session":"sensitive-marker"}'
    encrypted = vault.encrypt(
        plaintext,
        associated_data=session_associated_data(user_id="user-1", platform="instagram"),
    )

    assert encrypted.key_id == "test-key"
    assert b"sensitive-marker" not in encrypted.payload
    assert "sensitive-marker" not in repr(encrypted)
    assert (
        vault.decrypt(
            encrypted,
            associated_data=session_associated_data(user_id="user-1", platform="instagram"),
        )
        == plaintext
    )


def test_session_vault_rejects_wrong_associated_data() -> None:
    vault = SessionVault.from_base64_key(
        base64.b64encode(b"1" * 32).decode("ascii"),
        key_id="test-key",
    )
    encrypted = vault.encrypt(
        b"secret",
        associated_data=session_associated_data(user_id="user-1", platform="instagram"),
    )

    with pytest.raises(InvalidTag):
        vault.decrypt(
            encrypted,
            associated_data=session_associated_data(user_id="user-2", platform="instagram"),
        )


def test_session_vault_rejects_invalid_key_length() -> None:
    with pytest.raises(ValueError):
        SessionVault.from_base64_key(base64.b64encode(b"short").decode("ascii"), key_id="bad")


def test_session_vault_rejects_wrong_key_id() -> None:
    vault = SessionVault.from_base64_key(
        base64.b64encode(b"2" * 32).decode("ascii"),
        key_id="current",
    )

    with pytest.raises(ValueError):
        vault.decrypt(
            EncryptedSession(key_id="old", payload=b'{"key_id":"old"}'),
            associated_data=b"",
        )
