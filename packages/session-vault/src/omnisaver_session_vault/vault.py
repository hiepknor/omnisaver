from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class EncryptedSession:
    key_id: str
    payload: bytes = field(repr=False)


@dataclass(frozen=True)
class SessionVault:
    master_key: bytes = field(repr=False)
    key_id: str

    @classmethod
    def from_base64_key(cls, master_key_base64: str, *, key_id: str) -> SessionVault:
        try:
            master_key = base64.b64decode(master_key_base64, validate=True)
        except ValueError as exc:
            raise ValueError("SESSION_VAULT_MASTER_KEY_BASE64 must be valid base64") from exc
        if len(master_key) != 32:
            raise ValueError("SESSION_VAULT_MASTER_KEY_BASE64 must decode to 32 bytes")
        return cls(master_key=master_key, key_id=key_id)

    @staticmethod
    def generate_master_key_base64() -> str:
        return base64.b64encode(os.urandom(32)).decode("ascii")

    def encrypt(self, plaintext: bytes, *, associated_data: bytes) -> EncryptedSession:
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.master_key).encrypt(nonce, plaintext, associated_data)
        envelope = {
            "v": 1,
            "alg": "AES-256-GCM",
            "key_id": self.key_id,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        return EncryptedSession(
            key_id=self.key_id,
            payload=json.dumps(envelope, sort_keys=True).encode("utf-8"),
        )

    def decrypt(self, encrypted: EncryptedSession, *, associated_data: bytes) -> bytes:
        envelope = json.loads(encrypted.payload.decode("utf-8"))
        if envelope["key_id"] != self.key_id:
            raise ValueError("encrypted session key id does not match this vault")
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        return AESGCM(self.master_key).decrypt(nonce, ciphertext, associated_data)


def session_associated_data(*, user_id: str, platform: str) -> bytes:
    return f"user_id={user_id};platform={platform}".encode()
