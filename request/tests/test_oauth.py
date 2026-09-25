import json
import time

import pytest

from request.models import LLMModel
from request.oauth import (
    _b64url,
    authorization_url,
    build_pkce,
    decode_chatgpt_identity,
    load_fresh_openai_tokens,
    login_openai,
    save_token_file,
)
from request.services import (
    RequestError,
    auth_status,
    complete_single_turn,
    load_curated_catalog,
    sync_model_catalog,
)
from request.tests.fakes import FakeOpenAIClient, make_model

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def fake_access_token(account_id="acct-1", plan_type="plus", email="user@example.com"):
    header = _b64url(json.dumps({"alg": "none"}).encode("utf-8"))
    payload = _b64url(
        json.dumps(
            {
                "https://api.openai.com/auth": {
                    "chatgpt_account_id": account_id,
                    "chatgpt_plan_type": plan_type,
                },
                "https://api.openai.com/profile": {"email": email},
            }
        ).encode("utf-8")
    )
    return f"{header}.{payload}.sig"


def token_payload(**overrides):
    data = {
        "provider": "openai",
        "access_token": fake_access_token(),
        "refresh_token": "rt-old",
        "expires_at": time.time() + 3600,
        "account_id": "acct-1",
        "email": "user@example.com",
        "plan_type": "plus",
    }
    data.update(overrides)
    return data


def test_build_pkce_challenge_is_s256():
    verifier, challenge = build_pkce()
    assert verifier
    assert challenge
    assert verifier != challenge
    url = authorization_url(challenge, "state-1")
    assert "code_challenge_method=S256" in url
    assert "client_id=app_EMoamEEZ73f0CkXaXp7hrann" in url
    assert "localhost%3A8765" in url


def test_decode_chatgpt_identity_from_jwt():
    identity = decode_chatgpt_identity(fake_access_token(plan_type="go"))
    assert identity["account_id"] == "acct-1"
    assert identity["plan_type"] == "go"
    assert identity["email"] == "user@example.com"


def test_auth_status_logged_out(settings):
    result = auth_status("openai", auth_dir=settings.AUTH_DIR)
    assert result["logged_in"] is False
    assert result["provider"] == "openai"


def test_auth_status_rejects_other_provider():
    with pytest.raises(RequestError, match="not implemented"):
        auth_status("anthropic")


def test_refresh_persists_new_tokens(settings):
    save_token_file(
        token_payload(expires_at=time.time() - 10),
        settings.AUTH_DIR,
    )

    def post_token(body):
        assert body["grant_type"] == "refresh_token"
        return {
            "access_token": fake_access_token(account_id="acct-2", plan_type="plus"),
            "refresh_token": "rt-new",
            "expires_in": 3600,
        }

    tokens = load_fresh_openai_tokens(settings.AUTH_DIR, post_token=post_token)
    assert tokens["account_id"] == "acct-2"
    assert tokens["refresh_token"] == "rt-new"
    saved = json.loads((settings.AUTH_DIR / "openai.json").read_text(encoding="utf-8"))
    assert saved["refresh_token"] == "rt-new"
    assert "access_token" in saved


def test_login_openai_saves_tokens(settings):
    def post_token(body):
        assert body["grant_type"] == "authorization_code"
        assert body["code"] == "the-code"
        return {
            "access_token": fake_access_token(),
            "refresh_token": "rt-login",
            "expires_in": 3600,
        }

    result = login_openai(
        "openai",
        auth_dir=settings.AUTH_DIR,
        open_browser=lambda url: None,
        wait_for_code=lambda state: "the-code",
        post_token=post_token,
    )
    assert result["logged_in"] is True
    assert result["plan_type"] == "plus"
    assert "access_token" not in result
    assert (settings.AUTH_DIR / "openai.json").is_file()


def test_complete_single_turn_uses_api_key_for_chat_model():
    make_model()
    client = FakeOpenAIClient([])
    result = complete_single_turn(
        "why is the sky blue?",
        openai_client=client,
        auth_mode="auto",
    )
    assert result["auth_mode"] == "api_key"
    assert result["estimated_cost_usd"] is not None
    assert client.chat_calls


def test_complete_single_turn_oauth_rejected_for_chat_completions():
    make_model()
    with pytest.raises(RequestError, match="does not support ChatGPT OAuth"):
        complete_single_turn(
            "hi",
            openai_client=FakeOpenAIClient([]),
            auth_mode="oauth",
        )


def test_complete_single_turn_auto_uses_oauth_when_supported(settings):
    make_model(
        model_id="gpt-5.6-terra",
        endpoint_kind=LLMModel.EndpointKind.RESPONSES,
        is_default=True,
        extra_params={"supports_codex_oauth": True},
        max_output_tokens=128000,
    )
    save_token_file(token_payload(), settings.AUTH_DIR)
    client = FakeOpenAIClient([])
    result = complete_single_turn(
        "hello",
        openai_client=client,
        auth_mode="auto",
        auth_dir=settings.AUTH_DIR,
    )
    assert result["auth_mode"] == "oauth"
    assert result["estimated_cost_usd"] is None
    assert client.response_calls
    assert client.response_calls[0]["store"] is False


def test_complete_single_turn_oauth_without_login(settings):
    make_model(
        model_id="gpt-5.6-terra",
        endpoint_kind=LLMModel.EndpointKind.RESPONSES,
        is_default=True,
        extra_params={"supports_codex_oauth": True},
        max_output_tokens=128000,
    )
    with pytest.raises(RequestError, match="Not logged in"):
        complete_single_turn(
            "hello",
            openai_client=FakeOpenAIClient([]),
            auth_mode="oauth",
            auth_dir=settings.AUTH_DIR,
        )


def test_catalog_marks_terra_for_codex_oauth():
    models = load_curated_catalog()
    terra = next(row for row in models if row["model_id"] == "gpt-5.6-terra")
    assert terra["supports_codex_oauth"] is True


def test_sync_copies_supports_codex_oauth(tmp_path):
    catalog = tmp_path / "openai_models.json"
    catalog.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "model_id": "gpt-5.6-terra",
                        "display_name": "gpt-5.6-terra",
                        "endpoint_kind": "responses",
                        "supports_codex_oauth": True,
                        "is_default": True,
                        "modalities": ["text"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    sync_model_catalog(
        catalog_file=catalog, openai_client=FakeOpenAIClient(["gpt-5.6-terra"])
    )
    obj = LLMModel.objects.get(model_id="gpt-5.6-terra")
    assert obj.extra_params.get("supports_codex_oauth") is True
