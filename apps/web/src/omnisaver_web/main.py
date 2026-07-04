from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from omnisaver_config import Settings, load_settings
from omnisaver_db import InMemorySessionRepository
from omnisaver_session_vault import SessionVault
from omnisaver_web.session_portal import BasicSessionValidator, PortalDependencies, create_app


def build_app(settings: Settings) -> FastAPI:
    vault = SessionVault.from_base64_key(
        settings.session_vault_master_key_base64,
        key_id=settings.cookie_encryption_key_id,
    )
    return create_app(
        PortalDependencies(
            repository=InMemorySessionRepository(),
            vault=vault,
            validator=BasicSessionValidator(),
        )
    )


def main() -> None:
    settings = load_settings()
    uvicorn.run(build_app(settings), host="0.0.0.0", port=8000)
