"""ChatGPT/Codex OAuth helpers. Commands call request.services, not this module."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from django.conf import settings

PROVIDER_OPENAI = "openai"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
ORIGINATOR = "my_agent_v1"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8765
CALLBACK_PATH = "/auth/callback"
SCOPE = "openid profile email offline_access"
REFRESH_SKEW_SECONDS = 60
LOGIN_TIMEOUT_SECONDS = 300
TOKEN_HTTP_TIMEOUT = 30

AUTH_AUTO = "auto"
AUTH_OAUTH = "oauth"
AUTH_API_KEY = "api_key"
AUTH_MODES = (AUTH_AUTO, AUTH_OAUTH, AUTH_API_KEY)


def _raise(message: str, cause: BaseException | None = None):
    from request.services import RequestError

    if cause is not None:
        raise RequestError(message) from cause
    raise RequestError(message)


def ensure_oauth_provider(provider: str | None) -> str:
    value = (provider or PROVIDER_OPENAI).strip().lower() or PROVIDER_OPENAI
    if value != PROVIDER_OPENAI:
        _raise(f"OAuth for provider {value!r} is not implemented.")
    return value


def auth_dir_path(auth_dir: Path | None = None) -> Path:
    if auth_dir is not None:
        return Path(auth_dir)
    return Path(settings.AUTH_DIR)


def token_path(provider: str = PROVIDER_OPENAI, auth_dir: Path | None = None) -> Path:
    provider = ensure_oauth_provider(provider)
    return auth_dir_path(auth_dir) / f"{provider}.json"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def build_pkce() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def redirect_uri(port: int = CALLBACK_PORT) -> str:
    return f"http://localhost:{port}{CALLBACK_PATH}"


def authorization_url(
    challenge: str,
    state: str,
    *,
    port: int = CALLBACK_PORT,
) -> str:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri(port),
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": ORIGINATOR,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def decode_chatgpt_identity(access_token: str) -> dict:
    empty = {"account_id": None, "email": None, "plan_type": None}
    parts = access_token.split(".")
    if len(parts) != 3:
        return empty
    payload_b64 = parts[1]
    pad = "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(payload_b64 + pad).decode("utf-8")
        )
    except (ValueError, json.JSONDecodeError):
        return empty
    if not isinstance(payload, dict):
        return empty
    auth = payload.get("https://api.openai.com/auth")
    profile = payload.get("https://api.openai.com/profile")
    auth = auth if isinstance(auth, dict) else {}
    profile = profile if isinstance(profile, dict) else {}
    account_id = auth.get("chatgpt_account_id")
    email = profile.get("email")
    plan_type = auth.get("chatgpt_plan_type")
    return {
        "account_id": account_id if isinstance(account_id, str) and account_id else None,
        "email": email if isinstance(email, str) and email else None,
        "plan_type": plan_type if isinstance(plan_type, str) and plan_type else None,
    }


def tokens_from_oauth_response(payload: dict) -> dict:
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    if not access or not refresh or expires_in is None:
        _raise("ChatGPT token response is missing access_token, refresh_token, or expires_in.")
    identity = decode_chatgpt_identity(access)
    if not identity["account_id"]:
        _raise("Failed to extract account id from ChatGPT access token.")
    return {
        "provider": PROVIDER_OPENAI,
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": time.time() + float(expires_in),
        "account_id": identity["account_id"],
        "email": identity["email"],
        "plan_type": identity["plan_type"],
    }


def public_auth_status(tokens: dict | None) -> dict:
    if not tokens:
        return {
            "provider": PROVIDER_OPENAI,
            "logged_in": False,
            "expired": False,
            "plan_type": None,
            "email": None,
            "expires_at": None,
        }
    expired = is_access_expired(tokens)
    expires_at = tokens.get("expires_at")
    expires_iso = None
    if expires_at is not None:
        expires_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(expires_at)))
    return {
        "provider": tokens.get("provider") or PROVIDER_OPENAI,
        "logged_in": True,
        "expired": expired,
        "plan_type": tokens.get("plan_type"),
        "email": tokens.get("email"),
        "expires_at": expires_iso,
    }


def load_token_file(
    provider: str = PROVIDER_OPENAI, auth_dir: Path | None = None
) -> dict | None:
    path = token_path(provider, auth_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _raise(f"Auth file is not valid JSON: {path}", exc)
    if not isinstance(payload, dict):
        _raise(f"Auth file must be a JSON object: {path}")
    return payload


def save_token_file(tokens: dict, auth_dir: Path | None = None) -> Path:
    provider = ensure_oauth_provider(tokens.get("provider"))
    path = token_path(provider, auth_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(tokens, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def is_access_expired(tokens: dict, now: float | None = None) -> bool:
    expires_at = tokens.get("expires_at")
    if expires_at is None:
        return True
    current = time.time() if now is None else now
    try:
        return current >= float(expires_at) - REFRESH_SKEW_SECONDS
    except (TypeError, ValueError):
        return True


def post_token_request(body: dict) -> dict:
    encoded = urllib.parse.urlencode(body).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": ORIGINATOR,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TOKEN_HTTP_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        _raise(f"ChatGPT token request failed ({exc.code}). {detail}".strip())
    except urllib.error.URLError as exc:
        _raise(f"ChatGPT token request failed: {exc}", exc)
    except json.JSONDecodeError as exc:
        _raise("ChatGPT token response is not valid JSON.", exc)
    if not isinstance(payload, dict):
        _raise("ChatGPT token response must be a JSON object.")
    return payload


def exchange_authorization_code(
    code: str,
    verifier: str,
    *,
    port: int = CALLBACK_PORT,
    post_token=None,
) -> dict:
    sender = post_token or post_token_request
    payload = sender(
        {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri(port),
        }
    )
    return tokens_from_oauth_response(payload)


def refresh_openai_tokens(refresh_token: str, *, post_token=None) -> dict:
    sender = post_token or post_token_request
    payload = sender(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
        }
    )
    return tokens_from_oauth_response(payload)


def load_fresh_openai_tokens(
    auth_dir: Path | None = None,
    *,
    post_token=None,
    force_refresh: bool = False,
) -> dict | None:
    tokens = load_token_file(PROVIDER_OPENAI, auth_dir)
    if not tokens:
        return None
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        _raise("OpenAI auth file is missing refresh_token. Run auth_login again.")
    if force_refresh or is_access_expired(tokens):
        refreshed = refresh_openai_tokens(refresh_token, post_token=post_token)
        save_token_file(refreshed, auth_dir)
        return refreshed
    if not tokens.get("access_token") or not tokens.get("account_id"):
        _raise("OpenAI auth file is missing access_token or account_id. Run auth_login again.")
    return tokens


def provider_auth_status(
    provider: str | None = None, auth_dir: Path | None = None
) -> dict:
    provider = ensure_oauth_provider(provider)
    tokens = load_token_file(provider, auth_dir)
    return public_auth_status(tokens)


def wait_for_oauth_callback(
    expected_state: str,
    *,
    port: int = CALLBACK_PORT,
    timeout: int = LOGIN_TIMEOUT_SECONDS,
) -> str:
    result: dict = {"code": None, "error": None}
    ready = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != CALLBACK_PATH:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return
            params = urllib.parse.parse_qs(parsed.query)
            state = (params.get("state") or [None])[0]
            code = (params.get("code") or [None])[0]
            error = (params.get("error") or [None])[0]
            if error:
                result["error"] = error
                body = b"Login failed. You can close this tab."
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                ready.set()
                return
            if state != expected_state or not code:
                body = b"State mismatch or missing code."
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            result["code"] = code
            body = b"Login complete. You can close this tab."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            ready.set()

    try:
        server = HTTPServer((CALLBACK_HOST, port), Handler)
    except OSError as exc:
        _raise(f"Could not bind OAuth callback on {CALLBACK_HOST}:{port}: {exc}", exc)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if not ready.wait(timeout):
            _raise(
                "Timed out waiting for ChatGPT login. Open the printed URL and try again."
            )
    finally:
        server.shutdown()
        server.server_close()
    if result["error"]:
        _raise(f"ChatGPT login failed: {result['error']}")
    if not result["code"]:
        _raise("ChatGPT login did not return an authorization code.")
    return result["code"]


def login_openai(
    provider: str | None = None,
    *,
    auth_dir: Path | None = None,
    open_browser=None,
    wait_for_code=None,
    post_token=None,
    announce_url=None,
    port: int = CALLBACK_PORT,
) -> dict:
    provider = ensure_oauth_provider(provider)
    verifier, challenge = build_pkce()
    state = secrets.token_hex(16)
    url = authorization_url(challenge, state, port=port)
    if announce_url:
        announce_url(url)
    opener = open_browser if open_browser is not None else webbrowser.open
    opener(url)
    waiter = wait_for_code or (
        lambda expected_state: wait_for_oauth_callback(expected_state, port=port)
    )
    code = waiter(state)
    tokens = exchange_authorization_code(
        code, verifier, port=port, post_token=post_token
    )
    save_token_file(tokens, auth_dir)
    return public_auth_status(tokens)
