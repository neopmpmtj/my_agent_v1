import json
from io import StringIO

import pytest
from django.core.management import call_command

from request.models import LLMModel
from request.oauth import save_token_file
from request.tests.fakes import FakeOpenAIClient, make_model
from request.tests.test_oauth import fake_access_token, token_payload

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_auth_status_json_logged_out():
    out = StringIO()
    call_command("auth_status", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["logged_in"] is False
    assert payload["provider"] == "openai"
    assert "access_token" not in payload


def test_auth_status_json_logged_in(settings):
    save_token_file(token_payload(), settings.AUTH_DIR)
    out = StringIO()
    call_command("auth_status", "--provider", "openai", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["logged_in"] is True
    assert payload["plan_type"] == "plus"
    assert "access_token" not in json.dumps(payload)
    assert "refresh_token" not in json.dumps(payload)


def test_auth_status_unknown_provider_json():
    out = StringIO()
    with pytest.raises(SystemExit) as exc:
        call_command("auth_status", "--provider", "anthropic", "--json", stdout=out)
    assert exc.value.code == 1
    payload = json.loads(out.getvalue())
    assert payload["ok"] is False
    assert "not implemented" in payload["error"]


def test_auth_login_json(monkeypatch, settings):
    def fake_login(provider, **kwargs):
        from request.services import auth_login as real

        def post_token(body):
            return {
                "access_token": fake_access_token(),
                "refresh_token": "rt-cli",
                "expires_in": 3600,
            }

        return real(
            provider,
            auth_dir=settings.AUTH_DIR,
            open_browser=lambda url: None,
            wait_for_code=lambda state: "code-1",
            post_token=post_token,
            announce_url=kwargs.get("announce_url"),
        )

    monkeypatch.setattr(
        "request.management.commands.auth_login.auth_login", fake_login
    )
    out = StringIO()
    err = StringIO()
    call_command("auth_login", "--json", stdout=out, stderr=err)
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["logged_in"] is True
    assert "access_token" not in payload
    saved = json.loads((settings.AUTH_DIR / "openai.json").read_text(encoding="utf-8"))
    assert saved["refresh_token"] == "rt-cli"


def test_llm_ask_json_includes_auth_mode(monkeypatch):
    make_model()
    client = FakeOpenAIClient([])

    def fake_complete(**kwargs):
        from request.services import complete_single_turn

        return complete_single_turn(**kwargs, openai_client=client)

    monkeypatch.setattr(
        "request.management.commands.llm_ask.complete_single_turn", fake_complete
    )
    out = StringIO()
    call_command(
        "llm_ask",
        "--prompt",
        "why is the sky blue?",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    assert payload["auth_mode"] == "api_key"


def test_llm_ask_oauth_json(monkeypatch, settings):
    make_model(
        model_id="gpt-5.6-terra",
        endpoint_kind=LLMModel.EndpointKind.RESPONSES,
        extra_params={"supports_codex_oauth": True},
        max_output_tokens=128000,
        is_default=True,
    )
    save_token_file(token_payload(), settings.AUTH_DIR)
    client = FakeOpenAIClient([])

    def fake_complete(**kwargs):
        from request.services import complete_single_turn

        kwargs["auth_dir"] = settings.AUTH_DIR
        return complete_single_turn(**kwargs, openai_client=client)

    monkeypatch.setattr(
        "request.management.commands.llm_ask.complete_single_turn", fake_complete
    )
    out = StringIO()
    call_command(
        "llm_ask",
        "--prompt",
        "hi",
        "--model",
        "gpt-5.6-terra",
        "--auth",
        "oauth",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["auth_mode"] == "oauth"
    assert payload["estimated_cost_usd"] is None
    assert payload["text"] == "via responses"
