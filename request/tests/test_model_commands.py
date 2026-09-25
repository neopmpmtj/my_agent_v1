import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from request.models import LLMModel
from request.tests.fakes import FakeOpenAIClient, make_model

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_model_list_json_empty():
    out = StringIO()
    call_command("model_list", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["entity"] == "llm_model"
    assert payload["count"] == 0
    assert payload["items"] == []


def test_model_list_json_includes_endpoint_kinds():
    make_model()
    make_model(
        model_id="o3-mini",
        endpoint_kind=LLMModel.EndpointKind.RESPONSES,
        is_default=False,
    )
    out = StringIO()
    call_command("model_list", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["count"] == 2
    assert set(payload["endpoint_kinds_in_catalog"]) == {
        "chat_completions",
        "responses",
    }


def test_model_show_json():
    make_model()
    out = StringIO()
    call_command("model_show", "--model", "gpt-4o-mini", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["model"]["model_id"] == "gpt-4o-mini"
    assert payload["cli_defaults"]["max_output_tokens"] == 16384


def test_model_show_unknown_json():
    out = StringIO()
    with pytest.raises(SystemExit) as exc:
        call_command("model_show", "--model", "missing", "--json", stdout=out)
    assert exc.value.code == 1
    payload = json.loads(out.getvalue())
    assert payload == {"ok": False, "error": "Unknown model: missing"}


def test_llm_ask_json(monkeypatch):
    make_model()
    client = FakeOpenAIClient([])

    def fake_complete(**kwargs):
        from request.services import complete_single_turn

        return complete_single_turn(**kwargs, openai_client=client)

    monkeypatch.setattr("request.management.commands.llm_ask.complete_single_turn", fake_complete)
    out = StringIO()
    call_command(
        "llm_ask",
        "--prompt",
        "why is the sky blue?",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["text"] == "sky is blue"
    assert payload["model_id"] == "gpt-4o-mini"
    assert payload["endpoint_kind"] == "chat_completions"
    assert payload["usage"]["input_tokens"] == 8


def test_llm_ask_requires_prompt():
    with pytest.raises(CommandError):
        call_command("llm_ask")


def test_model_sync_json(monkeypatch, tmp_path):
    catalog = tmp_path / "openai_models.json"
    catalog.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "model_id": "gpt-4o-mini",
                        "display_name": "GPT-4o mini",
                        "endpoint_kind": "chat_completions",
                        "input_cost_per_1m": "0.15",
                        "output_cost_per_1m": "0.60",
                        "is_default": True,
                        "modalities": ["text"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    client = FakeOpenAIClient(["gpt-4o-mini"])

    def fake_sync(**kwargs):
        from request.services import sync_model_catalog

        return sync_model_catalog(catalog_file=catalog, openai_client=client)

    monkeypatch.setattr("request.management.commands.model_sync.sync_model_catalog", fake_sync)
    out = StringIO()
    call_command("model_sync", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["added"] == 1
    assert LLMModel.objects.filter(model_id="gpt-4o-mini", is_active=True).exists()


def test_model_add_json(monkeypatch, tmp_path):
    catalog = tmp_path / "openai_models.json"
    catalog.write_text(json.dumps({"_comment": "test", "models": []}), encoding="utf-8")
    table = {
        "openai/gpt-5-mini": {
            "input_cost_per_token": 0.00000025,
            "output_cost_per_token": 0.000002,
        }
    }
    client = FakeOpenAIClient(["gpt-5-mini"])

    def fake_add(model_id, **kwargs):
        from request.services import add_model_to_stack

        return add_model_to_stack(
            model_id,
            catalog_file=catalog,
            openai_client=client,
            price_table=table,
            input_cost_per_1m=kwargs.get("input_cost_per_1m"),
            output_cost_per_1m=kwargs.get("output_cost_per_1m"),
            endpoint_kind=kwargs.get("endpoint_kind"),
            is_default=kwargs.get("is_default", False),
        )

    monkeypatch.setattr("request.management.commands.model_add.add_model_to_stack", fake_add)
    out = StringIO()
    call_command("model_add", "--model", "gpt-5-mini", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["model_id"] == "gpt-5-mini"
    assert payload["endpoint_kind"] == "responses"
    assert LLMModel.objects.filter(model_id="gpt-5-mini", is_active=True).exists()


def test_model_add_explicit_costs(monkeypatch, tmp_path):
    catalog = tmp_path / "openai_models.json"
    catalog.write_text(json.dumps({"models": []}), encoding="utf-8")
    client = FakeOpenAIClient(["gpt-4.1"])

    def fake_add(model_id, **kwargs):
        from request.services import add_model_to_stack

        return add_model_to_stack(
            model_id,
            catalog_file=catalog,
            openai_client=client,
            input_cost_per_1m=kwargs.get("input_cost_per_1m"),
            output_cost_per_1m=kwargs.get("output_cost_per_1m"),
            endpoint_kind=kwargs.get("endpoint_kind") or "chat_completions",
            is_default=kwargs.get("is_default", False),
        )

    monkeypatch.setattr("request.management.commands.model_add.add_model_to_stack", fake_add)
    out = StringIO()
    call_command(
        "model_add",
        "--model",
        "gpt-4.1",
        "--input-cost-per-1m",
        "2.00",
        "--output-cost-per-1m",
        "8.00",
        "--endpoint-kind",
        "chat_completions",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["input_cost_per_1m"] == "2.00"
    assert payload["output_cost_per_1m"] == "8.00"


def test_model_remove_json(monkeypatch, tmp_path):
    catalog = tmp_path / "openai_models.json"
    catalog.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "model_id": "gpt-4o-mini",
                        "endpoint_kind": "chat_completions",
                        "is_default": True,
                        "modalities": ["text"],
                    },
                    {
                        "model_id": "gpt-4o",
                        "endpoint_kind": "chat_completions",
                        "is_default": False,
                        "modalities": ["text"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    client = FakeOpenAIClient(["gpt-4o-mini", "gpt-4o"])

    def fake_remove(model_id, **kwargs):
        from request.services import remove_model_from_stack

        return remove_model_from_stack(
            model_id, catalog_file=catalog, openai_client=client
        )

    monkeypatch.setattr(
        "request.management.commands.model_remove.remove_model_from_stack",
        fake_remove,
    )
    out = StringIO()
    call_command("model_remove", "--model", "gpt-4o", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["model_id"] == "gpt-4o"
    assert payload["removed"] is True
    assert not LLMModel.objects.get(model_id="gpt-4o").is_active
