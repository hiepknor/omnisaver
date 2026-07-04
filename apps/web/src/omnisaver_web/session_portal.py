from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Protocol
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from omnisaver_db import SessionRepository
from omnisaver_session_vault import SessionVault, session_associated_data


class SessionValidator(Protocol):
    def validate(self, *, platform: str, session_payload: str) -> None:
        pass


class BasicSessionValidator:
    def validate(self, *, platform: str, session_payload: str) -> None:
        if platform not in {"instagram", "pinterest", "facebook"}:
            raise ValueError("Unsupported connect platform.")
        payload = session_payload.strip()
        if not payload:
            raise ValueError("Session payload is required.")
        if platform == "instagram":
            _validate_netscape_cookies(
                payload=payload,
                platform=platform,
                required_cookie_names={"sessionid", "csrftoken", "ds_user_id"},
            )


def _validate_netscape_cookies(
    *,
    payload: str,
    platform: str,
    required_cookie_names: set[str],
) -> None:
    cookie_names: set[str] = set()
    has_matching_domain = False
    for line in payload.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 7:
            raise ValueError("Cookie phải ở định dạng Netscape cookies.txt.")
        domain = parts[0].lstrip("#").lower()
        name = parts[5].strip()
        if domain == f"{platform}.com" or domain.endswith(f".{platform}.com"):
            has_matching_domain = True
            cookie_names.add(name)
    if not has_matching_domain:
        raise ValueError(f"Cookie phải chứa domain {platform}.com.")
    missing = sorted(required_cookie_names - cookie_names)
    if missing:
        names = ", ".join(missing)
        raise ValueError(f"Cookie {platform} thiếu: {names}.")


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


PLATFORM_LABELS = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "pinterest": "Pinterest",
}

PLATFORM_GUIDANCE = {
    "facebook": "Dùng session từ tài khoản Facebook có quyền xem link bạn muốn tải.",
    "instagram": "Dùng session từ tài khoản Instagram có quyền xem reel, post hoặc story.",
    "pinterest": "Dùng session từ tài khoản Pinterest có quyền xem pin hoặc board.",
}

PLATFORM_LOGIN_URLS = {
    "facebook": "https://www.facebook.com/login/",
    "instagram": "https://www.instagram.com/accounts/login/",
    "pinterest": "https://www.pinterest.com/login/",
}


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
    ) -> HTMLResponse:
        record = deps.repository.get_valid_connect_token(token=token, platform=platform)
        if record is None:
            return HTMLResponse(
                _render_status_page(
                    title="Link kết nối không hợp lệ",
                    body=(
                        "Link này đã hết hạn, đã được sử dụng hoặc không đúng nền tảng. "
                        "Hãy quay lại Telegram và tạo link kết nối mới."
                    ),
                    tone="warning",
                ),
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return HTMLResponse(_render_connect_page(platform=platform, token=token))

    @app.post("/connect/{platform}", response_model=None)
    async def post_connect_session(
        platform: str,
        request: Request,
        deps: PortalDependencies = portal_dependencies,
    ) -> dict[str, str] | HTMLResponse:
        wants_html = _request_wants_html(request)
        try:
            connect_request = await _connect_request_from_http_request(request)
        except ValidationError as exc:
            if wants_html:
                return HTMLResponse(
                    _render_connect_page(
                        platform=platform,
                        token="",
                        error="Vui lòng nhập session payload hợp lệ.",
                    ),
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            ) from exc
        record = deps.repository.get_valid_connect_token(
            token=connect_request.token,
            platform=platform,
        )
        if record is None:
            if wants_html:
                return HTMLResponse(
                    _render_status_page(
                        title="Link kết nối không hợp lệ",
                        body=(
                            "Link này đã hết hạn hoặc đã được sử dụng. "
                            "Hãy tạo link mới trong chat riêng với OmniSaver."
                        ),
                        tone="warning",
                    ),
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token.")
        try:
            deps.validator.validate(
                platform=platform,
                session_payload=connect_request.session_payload,
            )
        except ValueError as exc:
            if wants_html:
                return HTMLResponse(
                    _render_connect_page(
                        platform=platform,
                        token=connect_request.token,
                        error=str(exc),
                    ),
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        encrypted = deps.vault.encrypt(
            connect_request.session_payload.encode("utf-8"),
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
        deps.repository.mark_connect_token_used(token=connect_request.token)
        if wants_html:
            return HTMLResponse(
                _render_status_page(
                    title=f"Đã kết nối {PLATFORM_LABELS.get(platform, platform)}",
                    body=(
                        "Session của bạn đã được mã hóa và lưu an toàn. "
                        "Bạn có thể quay lại Telegram và gửi lại link cần tải."
                    ),
                    tone="success",
                )
            )
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


async def _connect_request_from_http_request(request: Request) -> ConnectSessionRequest:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        return ConnectSessionRequest.model_validate(payload)

    body = (await request.body()).decode("utf-8")
    values = parse_qs(body, keep_blank_values=True)
    return ConnectSessionRequest(
        token=_first_form_value(values, "token"),
        session_payload=_first_form_value(values, "session_payload"),
    )


def _first_form_value(values: dict[str, list[str]], key: str) -> str:
    items = values.get(key, [])
    if not items:
        return ""
    return items[0]


def _request_wants_html(request: Request) -> bool:
    content_type = request.headers.get("content-type", "")
    accept = request.headers.get("accept", "")
    return "application/json" not in content_type and "text/html" in accept


def _render_connect_page(*, platform: str, token: str, error: str | None = None) -> str:
    label = PLATFORM_LABELS.get(platform, platform.title())
    guidance = PLATFORM_GUIDANCE.get(
        platform,
        "Dùng session từ tài khoản có quyền xem nội dung trên nền tảng này.",
    )
    login_url = PLATFORM_LOGIN_URLS.get(platform)
    login_action = ""
    if login_url is not None:
        login_action = f"""
          <a class="login-link" href="{escape(login_url)}" target="_blank" rel="noreferrer">
            Mở {escape(label)} để đăng nhập
          </a>
        """
    error_html = ""
    if error is not None:
        error_html = f'<div class="notice notice-error">{escape(error)}</div>'
    disconnect_command = f"/disconnect {platform}"
    return _page_shell(
        title=f"Kết nối {label}",
        body=f"""
        <main class="panel">
          <div class="eyebrow">OmniSaver Session Portal</div>
          <h1>Kết nối {escape(label)}</h1>
          <p class="lead">
            Đăng nhập trên trang chính thức của {escape(label)}, lấy cookie/session từ trình
            duyệt của bạn, rồi dán vào ô bên dưới.
          </p>
          <p class="platform-note">{escape(guidance)}</p>
          <div class="notice notice-warning">
            Không nhập mật khẩu vào OmniSaver. OmniSaver không hiển thị form đăng nhập thay
            cho {escape(label)}.
          </div>
          {login_action}
          <section class="steps">
            <h2>Cách thực hiện</h2>
            <ol>
              <li>Mở {escape(label)} bằng nút bên dưới và đăng nhập trên trang chính thức.</li>
              <li>Lấy cookie/session của trình duyệt bằng công cụ bạn tin tưởng.</li>
              <li>Dán toàn bộ nội dung cookie/session vào ô này và bấm lưu.</li>
            </ol>
          </section>
          {error_html}
          <form method="post" action="/connect/{escape(platform)}" autocomplete="off">
            <input type="hidden" name="token" value="{escape(token)}" />
            <label for="session_payload">Cookie/session từ trình duyệt</label>
            <textarea
              id="session_payload"
              name="session_payload"
              rows="8"
              spellcheck="false"
              required
              placeholder="Dán cookie/session tại đây. Không dán mật khẩu."
            ></textarea>
            <button type="submit">Lưu session đã mã hóa</button>
          </form>
          <section class="guidance">
            <h2>Lưu ý bảo mật</h2>
            <ul>
              <li>Chỉ dùng session của tài khoản bạn sở hữu và có quyền truy cập nội dung.</li>
              <li>Session được mã hóa trước khi lưu, không đưa vào job payload.</li>
              <li>
                Bạn có thể thu hồi session trong Telegram bằng lệnh
                <code>{escape(disconnect_command)}</code>.
              </li>
            </ul>
          </section>
        </main>
        """,
    )


def _render_status_page(*, title: str, body: str, tone: str) -> str:
    return _page_shell(
        title=title,
        body=f"""
        <main class="panel panel-status">
          <div class="status-mark status-{escape(tone)}"></div>
          <h1>{escape(title)}</h1>
          <p class="lead">{escape(body)}</p>
        </main>
        """,
    )


def _page_shell(*, title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} - OmniSaver</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #172033;
      --muted: #607086;
      --line: #d8e0eb;
      --primary: #0f766e;
      --primary-dark: #115e59;
      --danger: #b42318;
      --success: #15803d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      background: var(--bg);
      color: var(--text);
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    .panel {{
      width: min(100%, 680px);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: clamp(20px, 5vw, 40px);
      box-shadow: 0 18px 60px rgba(23, 32, 51, 0.10);
    }}
    .panel-status {{ text-align: center; }}
    .eyebrow {{
      color: var(--primary);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0;
      margin-bottom: 8px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(28px, 5vw, 40px);
      line-height: 1.15;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .lead {{
      margin: 0 0 24px;
      color: var(--muted);
      font-size: 16px;
    }}
    .platform-note {{
      margin: -10px 0 20px;
      border-left: 3px solid var(--primary);
      padding: 10px 12px;
      background: #effaf8;
      color: var(--text);
      border-radius: 6px;
    }}
    .login-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      min-height: 44px;
      margin-bottom: 20px;
      border-radius: 8px;
      border: 1px solid var(--primary);
      color: var(--primary-dark);
      text-decoration: none;
      font-weight: 700;
    }}
    .login-link:hover {{ background: #effaf8; }}
    .steps {{
      margin-bottom: 22px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
    }}
    ol {{
      margin: 0;
      padding-left: 20px;
      color: var(--muted);
    }}
    ol li + li {{ margin-top: 8px; }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-weight: 700;
    }}
    textarea {{
      width: 100%;
      min-height: 180px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      color: var(--text);
      font: 14px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    textarea:focus {{
      outline: 3px solid rgba(15, 118, 110, 0.18);
      border-color: var(--primary);
    }}
    button {{
      width: 100%;
      min-height: 46px;
      margin-top: 14px;
      border: 0;
      border-radius: 8px;
      background: var(--primary);
      color: white;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{ background: var(--primary-dark); }}
    .guidance {{
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid var(--line);
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
      color: var(--muted);
    }}
    li + li {{ margin-top: 8px; }}
    code {{
      padding: 2px 5px;
      border-radius: 5px;
      background: #eef3f7;
      color: var(--text);
    }}
    .notice {{
      margin-bottom: 16px;
      border-radius: 8px;
      padding: 12px 14px;
      font-weight: 600;
    }}
    .notice-error {{
      color: var(--danger);
      background: #fff1f0;
      border: 1px solid #ffd7d3;
    }}
    .notice-warning {{
      color: #7a3b00;
      background: #fff7ed;
      border: 1px solid #fed7aa;
    }}
    .status-mark {{
      width: 48px;
      height: 48px;
      border-radius: 999px;
      margin: 0 auto 16px;
      border: 10px solid #dbeafe;
    }}
    .status-success {{
      background: var(--success);
      border-color: #dcfce7;
    }}
    .status-warning {{
      background: var(--danger);
      border-color: #fee2e2;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""
