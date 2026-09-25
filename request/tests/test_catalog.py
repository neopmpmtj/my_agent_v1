import json

import pytest

from request.models import LLMModel
from request.services import (
    RequestError,
    add_model_to_stack,
    complete_single_turn,
    guess_endpoint_kind,
    is_non_text_model_id,
    list_llm_models,
    load_curated_catalog,
    lookup_litellm_row,
    per_token_to_per_1m,
    prices_from_litellm_row,
    sync_model_catalog,
)
from request.tests.fakes import FakeOpenAIClient, make_model

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_load_curated_catalog_from_app_package():
    models = load_curated_catalog()
    ids = {row["model_id"] for row in models}
    assert "gpt-4o-mini" in ids
    kinds = {row["endpoint_kind"] for row in models}
    assert "chat_completions" in kinds
    assert "responses" in kinds


def test_skips_image_and_audio_ids():
    assert is_non_text_model_id("dall-e-3")
    assert is_non_text_model_id("tts-1")
    assert is_non_text_model_id("whisper-1")
    assert not is_non_text_model_id("gpt-4o-mini")


def test_sync_merges_curated_file_with_api_list(tmp_path):
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
                    },
                    {
                        "model_id": "o3-mini",
                        "display_name": "o3-mini",
                        "endpoint_kind": "responses",
                        "input_cost_per_1m": "1.10",
                        "output_cost_per_1m": "4.40",
                        "is_default": False,
                        "modalities": ["text"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    client = FakeOpenAIClient(["gpt-4o-mini", "brand-new-chat", "dall-e-3"])
    result = sync_model_catalog(catalog_file=catalog, openai_client=client)

    mini = LLMModel.objects.get(model_id="gpt-4o-mini")
    assert mini.is_active
    assert mini.is_default
    assert str(mini.input_cost_per_1m) == "0.150000"

    unknown = LLMModel.objects.get(model_id="brand-new-chat")
    assert not unknown.is_active
    assert "not in openai_models.json" in unknown.catalog_notes

    assert not LLMModel.objects.filter(model_id="dall-e-3").exists()
    o3 = LLMModel.objects.get(model_id="o3-mini")
    assert "not returned by models.list" in o3.catalog_notes
    assert "brand-new-chat" in " ".join(result["warnings"])
    assert set(result["endpoint_kinds_in_catalog"]) == {"chat_completions", "responses"}


def test_list_llm_models_hides_inactive():
    make_model(model_id="live", is_default=True)
    make_model(model_id="dead", is_default=False, is_active=False)
    ids = [obj.model_id for obj in list_llm_models()]
    assert ids == ["live"]


def test_complete_single_turn_uses_chat_completions():
    make_model()
    client = FakeOpenAIClient([])
    result = complete_single_turn("why is the sky blue?", openai_client=client)
    assert result["text"] == "sky is blue"
    assert result["endpoint_kind"] == "chat_completions"
    assert client.chat_calls
    assert not client.response_calls
    assert result["usage"]["input_tokens"] == 8
    assert result["estimated_cost_usd"] is not None


def test_complete_single_turn_uses_responses():
    make_model(
        model_id="o3-mini",
        endpoint_kind=LLMModel.EndpointKind.RESPONSES,
        is_default=True,
        max_output_tokens=100000,
    )
    client = FakeOpenAIClient([])
    result = complete_single_turn("hello", openai_client=client)
    assert result["text"] == "via responses"
    assert result["endpoint_kind"] == "responses"
    assert client.response_calls
    assert not client.chat_calls


def test_complete_single_turn_rejects_over_cap():
    make_model(max_output_tokens=10)
    with pytest.raises(RequestError, match="exceeds model cap"):
        complete_single_turn("hi", max_output_tokens=50, openai_client=FakeOpenAIClient([]))


def test_guess_endpoint_kind():
    assert guess_endpoint_kind("gpt-4o-mini") == "chat_completions"
    assert guess_endpoint_kind("o3-mini") == "responses"
    assert guess_endpoint_kind("gpt-5-mini") == "responses"


def test_per_token_to_per_1m():
    assert per_token_to_per_1m("0.00000015") == "0.150000"
    assert per_token_to_per_1m("0.0000011") == "1.100000"


def test_lookup_litellm_row_openai_prefix():
    table = {
        "openai/gpt-5-mini": {
            "input_cost_per_token": 0.00000025,
            "output_cost_per_token": 0.000002,
            "max_input_tokens": 128000,
            "max_output_tokens": 16384,
        }
    }
    row = lookup_litellm_row("gpt-5-mini", table)
    in_cost, out_cost, max_in, max_out = prices_from_litellm_row(row)
    assert in_cost == "0.250000"
    assert out_cost == "2.000000"
    assert max_in == 128000
    assert max_out == 16384


def test_lookup_litellm_row_missing():
    with pytest.raises(RequestError, match="No LiteLLM prices"):
        lookup_litellm_row("no-such-model", {})


def test_add_model_to_stack_writes_json_and_activates(tmp_path):
    catalog = tmp_path / "openai_models.json"
    catalog.write_text(
        json.dumps(
            {
                "_comment": "test",
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
                ],
            }
        ),
        encoding="utf-8",
    )
    table = {
        "openai/gpt-5-mini": {
            "input_cost_per_token": 0.00000025,
            "output_cost_per_token": 0.000002,
            "max_input_tokens": 400000,
            "max_output_tokens": 128000,
        }
    }
    client = FakeOpenAIClient(["gpt-4o-mini", "gpt-5-mini"])
    result = add_model_to_stack(
        "gpt-5-mini",
        catalog_file=catalog,
        openai_client=client,
        price_table=table,
    )
    assert result["model_id"] == "gpt-5-mini"
    assert result["endpoint_kind"] == "responses"
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    ids = [row["model_id"] for row in payload["models"]]
    assert "gpt-5-mini" in ids
    added = LLMModel.objects.get(model_id="gpt-5-mini")
    assert added.is_active
    assert str(added.input_cost_per_1m) == "0.250000"


def test_add_model_to_stack_rejects_non_text():
    with pytest.raises(RequestError, match="non-text"):
        add_model_to_stack("dall-e-3")
