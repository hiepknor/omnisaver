from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from omnisaver_db import SessionRepository
from omnisaver_session_vault import SessionVault, session_associated_data


class SessionValidator(Protocol):
    def validate(self, *, platform: str, session_payload: str) -> None:
        pass


class BasicSessionValidator:
    def validate(self, *, platform: str, session_payload: str) -> None:
        if platform not in {"instagram", "pinterest", "facebook"}:
            raise ValueError("Unsupported connect platform.")
        if not session_payload.strip():
            raise ValueError("Session payload is required.")


class ConnectSessionRequest(BaseModel):
    token: str = Field(min_length=1)
    session_payload: str = Field(min_length=1)


class DisconnectRequest(BaseModel):
    telegram_user_id: int


@dataclass(frozen=True)
class PortalDependencies:
    repository: SessionRepository
    vault: SessionVault
    validator: SessionValidator


def create_app(dependencies: PortalDependencies) -> FastAPI:
    app = FastAPI(title="OmniSaver Session Portal")

    def get_dependencies() -> PortalDependencies:
        return dependencies
    portal_dependencies = Depends(get_dependencies)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/connect/{platform}")
    def get_connect_page(
        platform: str,
        token: str,
        deps: PortalDependencies = portal_dependencies,
    ) -> dict[str, str | int]:
        record = deps.repository.get_valid_connect_token(token=token, platform=platform)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token.")
        return {
            "platform": platform,
            "telegram_user_id": record.telegram_user_id,
            "status": "ready",
        }

    @app.post("/connect/{platform}")
    def post_connect_session(
        platform: str,
        request: ConnectSessionRequest,
        deps: PortalDependencies = portal_dependencies,
    ) -> dict[str, str]:
        record = deps.repository.get_valid_connect_token(token=request.token, platform=platform)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token.")
        try:
            deps.validator.validate(platform=platform, session_payload=request.session_payload)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        encrypted = deps.vault.encrypt(
            request.session_payload.encode("utf-8"),
            associated_data=session_associated_data(
                user_id=str(record.user_id),
                platform=platform,
            ),
        )
        deps.repository.store_encrypted_session(
            telegram_user_id=record.telegram_user_id,
            platform=platform,
            encrypted_session=encrypted.payload,
            encryption_key_id=encrypted.key_id,
        )
        deps.repository.mark_connect_token_used(token=request.token)
        return {"platform": platform, "status": "connected"}

    @app.post("/disconnect/{platform}")
    def post_disconnect_session(
        platform: str,
        request: DisconnectRequest,
        deps: PortalDependencies = portal_dependencies,
    ) -> dict[str, str]:
        try:
            deps.repository.revoke_session(
                telegram_user_id=request.telegram_user_id,
                platform=platform,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found.",
            ) from exc
        return {"platform": platform, "status": "revoked"}

    return app
