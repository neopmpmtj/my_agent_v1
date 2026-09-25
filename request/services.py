"""Business logic for the request app."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from request.models import LLMModel
from request.oauth import (
    AUTH_API_KEY,
    AUTH_AUTO,
    AUTH_MODES,
    AUTH_OAUTH,
    CODEX_BASE_URL,
    ORIGINATOR,
    load_fresh_openai_tokens,
    login_openai as _login_openai,
    provider_auth_status,
)

PROVIDER_OPENAI = "openai"
DEFAULT_MAX_OUTPUT_TOKENS = 1024
CATALOG_FILENAME = "openai_models.json"
LITELLM_PRICES_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
PER_MILLION = Decimal("1000000")

SKIP_SUBSTRINGS = (
    "dall-e",
    "dall_e",
    "tts-",
    "whisper",
    "gpt-image",
    "sora",
    "text-embedding",
    "text-moderation",
    "omni-moderation",
    "transcribe",
    "audio",
)

TEXT_MODALITY = "text"


class RequestError(Exception):
    """User-facing error from request services."""


def catalog_path() -> Path:
    return Path(__file__).resolve().parent / "catalog" / CATALOG_FILENAME


def is_non_text_model_id(model_id: str) -> bool:
    lowered = model_id.lower()
    return any(fragment in lowered for fragment in SKIP_SUBSTRINGS)


def load_catalog_document(path: Path | None = None) -> dict:
    source = path or catalog_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RequestError(f"Catalog file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise RequestError(f"Catalog file is not valid JSON: {source}") from exc
    if not isinstance(payload, dict):
        raise RequestError("Catalog JSON must be an object.")
    models = payload.get("models")
    if not isinstance(models, list):
        raise RequestError("Catalog JSON must contain a 'models' list.")
    return payload


def load_curated_catalog(path: Path | None = None) -> list[dict]:
    return load_catalog_document(path)["models"]


def write_catalog_document(payload: dict, path: Path | None = None) -> Path:
    source = path or catalog_path()
    source.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return source


def guess_endpoint_kind(model_id: str) -> str:
    lowered = model_id.lower()
    if lowered.startswith(("o1", "o3", "o4")) or lowered.startswith("gpt-5"):
        return LLMModel.EndpointKind.RESPONSES
    return LLMModel.EndpointKind.CHAT_COMPLETIONS


def per_token_to_per_1m(cost_per_token) -> str:
    value = (Decimal(str(cost_per_token)) * PER_MILLION).quantize(Decimal("0.000001"))
    return format(value, "f")


def fetch_litellm_price_table(url: str | None = None) -> dict:
    target = url or LITELLM_PRICES_URL
    request = urllib.request.Request(
        target,
        headers={"User-Agent": "my_agent_v1-model_add"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RequestError(f"Could not fetch LiteLLM prices: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RequestError("LiteLLM price table is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise RequestError("LiteLLM price table must be a JSON object.")
    return payload


def lookup_litellm_row(model_id: str, table: dict) -> dict:
    for key in (f"openai/{model_id}", model_id):
        row = table.get(key)
        if isinstance(row, dict) and row.get("input_cost_per_token") is not None:
            return row
    raise RequestError(
        f"No LiteLLM prices for {model_id}. "
        "Pass --input-cost-per-1m and --output-cost-per-1m."
    )


def prices_from_litellm_row(row: dict) -> tuple[str, str, int | None, int | None]:
    inp = row.get("input_cost_per_token")
    out = row.get("output_cost_per_token")
    if inp is None or out is None:
        raise RequestError("LiteLLM row is missing input or output token cost.")
    max_in = _int_or_none(row.get("max_input_tokens") or row.get("max_tokens"))
    max_out = _int_or_none(row.get("max_output_tokens"))
    return per_token_to_per_1m(inp), per_token_to_per_1m(out), max_in, max_out


def add_model_to_stack(
    model_id: str,
    *,
    input_cost_per_1m: str | None = None,
    output_cost_per_1m: str | None = None,
    endpoint_kind: str | None = None,
    is_default: bool = False,
    catalog_file: Path | None = None,
    openai_client=None,
    price_table: dict | None = None,
) -> dict:
    model_id = (model_id or "").strip()
    if not model_id:
        raise RequestError("model_id is required.")
    if is_non_text_model_id(model_id):
        raise RequestError(f"Refusing non-text model: {model_id}")

    warnings: list[str] = []
    exists = LLMModel.objects.filter(
        provider=PROVIDER_OPENAI, model_id=model_id
    ).exists()
    if not exists:
        warnings.append(
            f"{model_id} is not in the DB yet. Run model_sync first to confirm "
            "it appears on models.list."
        )

    has_in = input_cost_per_1m not in (None, "")
    has_out = output_cost_per_1m not in (None, "")
    max_in = None
    max_out = None
    if has_in ^ has_out:
        raise RequestError(
            "Pass both --input-cost-per-1m and --output-cost-per-1m, or neither."
        )
    if has_in and has_out:
        in_cost = str(input_cost_per_1m)
        out_cost = str(output_cost_per_1m)
    else:
        table = price_table if price_table is not None else fetch_litellm_price_table()
        row = lookup_litellm_row(model_id, table)
        in_cost, out_cost, max_in, max_out = prices_from_litellm_row(row)

    kind = endpoint_kind or guess_endpoint_kind(model_id)
    valid_kinds = {choice[0] for choice in LLMModel.EndpointKind.choices}
    if kind not in valid_kinds:
        raise RequestError(f"Unknown endpoint_kind: {kind}")

    path = catalog_file or catalog_path()
    document = load_catalog_document(path)
    models = document["models"]
    entry = None
    for item in models:
        if item.get("model_id") == model_id:
            entry = item
            break
    if entry is None:
        entry = {"model_id": model_id}
        models.append(entry)

    if is_default:
        for item in models:
            item["is_default"] = item.get("model_id") == model_id

    entry.update(
        {
            "display_name": entry.get("display_name") or model_id,
            "endpoint_kind": kind,
            "input_cost_per_1m": in_cost,
            "output_cost_per_1m": out_cost,
            "supports_json_mode": kind == LLMModel.EndpointKind.CHAT_COMPLETIONS,
            "is_agent_capable": True,
            "is_default": bool(is_default or entry.get("is_default")),
            "modalities": ["text"],
        }
    )
    if max_in is not None and not entry.get("max_input_tokens"):
        entry["max_input_tokens"] = max_in
    if max_out is not None and not entry.get("max_output_tokens"):
        entry["max_output_tokens"] = max_out

    write_catalog_document(document, path)
    sync_result = sync_model_catalog(catalog_file=path, openai_client=openai_client)
    warnings.extend(sync_result.get("warnings") or [])
    return {
        "model_id": model_id,
        "input_cost_per_1m": in_cost,
        "output_cost_per_1m": out_cost,
        "endpoint_kind": kind,
        "is_default": bool(entry.get("is_default")),
        "warnings": warnings,
        "sync": sync_result,
    }


def remove_model_from_stack(
    model_id: str,
    *,
    catalog_file: Path | None = None,
    openai_client=None,
) -> dict:
    model_id = (model_id or "").strip()
    if not model_id:
        raise RequestError("model_id is required.")

    path = catalog_file or catalog_path()
    document = load_catalog_document(path)
    models = document["models"]
    removed_entry = None
    remaining: list[dict] = []
    for item in models:
        if item.get("model_id") == model_id:
            removed_entry = item
        else:
            remaining.append(item)

    if removed_entry is None:
        raise RequestError(f"{model_id} is not in the curated catalog.")

    if not remaining:
        raise RequestError(
            "Cannot remove the only model from the curated catalog. "
            "Add another model first."
        )

    warnings: list[str] = []
    was_default = bool(removed_entry.get("is_default"))
    new_default_id = None
    if was_default:
        remaining[0]["is_default"] = True
        new_default_id = remaining[0].get("model_id")
        warnings.append(
            f"{model_id} was default; set {new_default_id} as is_default."
        )

    document["models"] = remaining
    write_catalog_document(document, path)
    sync_result = sync_model_catalog(catalog_file=path, openai_client=openai_client)
    warnings.extend(sync_result.get("warnings") or [])

    note = f"{model_id} was removed from openai_models.json."
    LLMModel.objects.filter(provider=PROVIDER_OPENAI, model_id=model_id).update(
        is_active=False,
        is_default=False,
        catalog_notes=note,
    )

    return {
        "model_id": model_id,
        "removed": True,
        "was_default": was_default,
        "new_default_id": new_default_id,
        "warnings": warnings,
        "sync": sync_result,
    }


def _openai_client(client=None):
    if client is not None:
        return client
    if not settings.OPENAI_API_KEY:
        raise RequestError("OPENAI_API_KEY is not set.")
    from openai import OpenAI

    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _codex_client(access_token: str, account_id: str):
    from openai import OpenAI

    return OpenAI(
        api_key=access_token,
        base_url=CODEX_BASE_URL,
        default_headers={
            "ChatGPT-Account-ID": account_id,
            "OpenAI-Beta": "responses=experimental",
            "originator": ORIGINATOR,
        },
    )


def _list_api_model_ids(client) -> set[str]:
    ids = set()
    for item in client.models.list():
        model_id = getattr(item, "id", None)
        if model_id:
            ids.add(model_id)
    return ids


def _decimal_or_none(value):
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _int_or_none(value):
    if value is None or value == "":
        return None
    return int(value)


def serialize_llm_model(obj: LLMModel) -> dict:
    return {
        "provider": obj.provider,
        "model_id": obj.model_id,
        "display_name": obj.display_name,
        "endpoint_kind": obj.endpoint_kind,
        "input_cost_per_1m": obj.input_cost_per_1m,
        "output_cost_per_1m": obj.output_cost_per_1m,
        "max_input_tokens": obj.max_input_tokens,
        "max_output_tokens": obj.max_output_tokens,
        "default_temperature": obj.default_temperature,
        "supports_json_mode": obj.supports_json_mode,
        "is_agent_capable": obj.is_agent_capable,
        "is_default": obj.is_default,
        "is_active": obj.is_active,
        "api_seen_at": obj.api_seen_at,
        "catalog_notes": obj.catalog_notes,
        "extra_params": obj.extra_params,
    }


def sync_model_catalog(catalog_file: Path | None = None, openai_client=None) -> dict:
    curated = load_curated_catalog(catalog_file)
    now = timezone.now()
    client = _openai_client(openai_client)
    api_ids = _list_api_model_ids(client)
    warnings: list[str] = []
    added = 0
    updated = 0
    curated_ids: set[str] = set()
    default_ids: list[str] = []

    for entry in curated:
        model_id = (entry.get("model_id") or "").strip()
        if not model_id:
            warnings.append("Skipped curated entry with empty model_id.")
            continue
        modalities = entry.get("modalities") or [TEXT_MODALITY]
        if TEXT_MODALITY not in modalities or is_non_text_model_id(model_id):
            warnings.append(f"Skipped non-text curated model: {model_id}")
            continue
        curated_ids.add(model_id)
        endpoint_kind = entry.get("endpoint_kind") or LLMModel.EndpointKind.CHAT_COMPLETIONS
        notes = []
        seen = model_id in api_ids
        if not seen:
            note = f"{model_id} is in the curated catalog but was not returned by models.list."
            notes.append(note)
            warnings.append(note)
        extra = dict(entry.get("extra_params") or {})
        if "supports_codex_oauth" in entry:
            extra["supports_codex_oauth"] = bool(entry["supports_codex_oauth"])
        defaults = {
            "display_name": entry.get("display_name") or model_id,
            "endpoint_kind": endpoint_kind,
            "input_cost_per_1m": _decimal_or_none(entry.get("input_cost_per_1m")),
            "output_cost_per_1m": _decimal_or_none(entry.get("output_cost_per_1m")),
            "max_input_tokens": _int_or_none(entry.get("max_input_tokens")),
            "max_output_tokens": _int_or_none(entry.get("max_output_tokens")),
            "default_temperature": entry.get("default_temperature"),
            "supports_json_mode": bool(entry.get("supports_json_mode", False)),
            "is_agent_capable": bool(entry.get("is_agent_capable", False)),
            "is_default": bool(entry.get("is_default", False)),
            "is_active": True,
            "api_seen_at": now if seen else None,
            "catalog_notes": " ".join(notes),
            "extra_params": extra,
        }
        obj, created = LLMModel.objects.update_or_create(
            provider=PROVIDER_OPENAI,
            model_id=model_id,
            defaults=defaults,
        )
        if created:
            added += 1
        else:
            updated += 1
        if obj.is_default:
            default_ids.append(model_id)

    if len(default_ids) > 1:
        keep = default_ids[0]
        LLMModel.objects.filter(provider=PROVIDER_OPENAI, is_default=True).exclude(
            model_id=keep
        ).update(is_default=False)
        warnings.append(
            f"Multiple curated defaults; kept {keep} as is_default."
        )

    skipped_non_text = 0
    for api_id in sorted(api_ids):
        if api_id in curated_ids:
            continue
        if is_non_text_model_id(api_id):
            skipped_non_text += 1
            continue
        note = f"{api_id} is on the API but not in openai_models.json."
        warnings.append(note)
        obj, created = LLMModel.objects.update_or_create(
            provider=PROVIDER_OPENAI,
            model_id=api_id,
            defaults={
                "display_name": api_id,
                "endpoint_kind": LLMModel.EndpointKind.CHAT_COMPLETIONS,
                "is_active": False,
                "is_default": False,
                "api_seen_at": now,
                "catalog_notes": note + " Add it to the curated catalog to activate.",
            },
        )
        if created:
            added += 1
        else:
            updated += 1

    kinds = list(
        LLMModel.objects.filter(provider=PROVIDER_OPENAI, is_active=True)
        .values_list("endpoint_kind", flat=True)
        .distinct()
        .order_by("endpoint_kind")
    )
    if len(kinds) > 1:
        warnings.append(
            "Catalog has mixed endpoint kinds: " + ", ".join(kinds)
        )

    return {
        "added": added,
        "updated": updated,
        "warnings": warnings,
        "api_count": len(api_ids),
        "curated_count": len(curated_ids),
        "skipped_non_text": skipped_non_text,
        "endpoint_kinds_in_catalog": kinds,
    }


def list_llm_models(provider: str = PROVIDER_OPENAI, active_only: bool = True) -> list[LLMModel]:
    qs = LLMModel.objects.filter(provider=provider)
    if active_only:
        qs = qs.filter(is_active=True)
    return list(qs)


def get_llm_model(model_id: str, provider: str = PROVIDER_OPENAI) -> LLMModel:
    try:
        return LLMModel.objects.get(provider=provider, model_id=model_id)
    except LLMModel.DoesNotExist as exc:
        raise RequestError(f"Unknown model: {model_id}") from exc


def resolve_model(model_id: str | None = None) -> tuple[LLMModel, list[str]]:
    warnings: list[str] = []
    if model_id:
        obj = get_llm_model(model_id)
        if not obj.is_active:
            raise RequestError(f"Model is inactive: {model_id}")
        return obj, warnings

    default = LLMModel.objects.filter(
        provider=PROVIDER_OPENAI, is_default=True, is_active=True
    ).first()
    if default:
        return default, warnings

    env_id = settings.OPENAI_MODEL
    try:
        obj = LLMModel.objects.get(
            provider=PROVIDER_OPENAI, model_id=env_id, is_active=True
        )
    except LLMModel.DoesNotExist as exc:
        raise RequestError(
            f"No default model in the catalog and OPENAI_MODEL={env_id!r} "
            "is not an active row. Run model_sync."
        ) from exc
    warnings.append(f"No is_default row; using OPENAI_MODEL={env_id}.")
    return obj, warnings


def model_supports_codex_oauth(model: LLMModel) -> bool:
    if model.endpoint_kind != LLMModel.EndpointKind.RESPONSES:
        return False
    extra = model.extra_params or {}
    return bool(extra.get("supports_codex_oauth"))


def auth_login(provider: str | None = None, **kwargs) -> dict:
    return _login_openai(provider, **kwargs)


def auth_status(provider: str | None = None, auth_dir=None) -> dict:
    return provider_auth_status(provider, auth_dir=auth_dir)


def resolve_auth_mode(
    model: LLMModel,
    auth_mode: str | None = None,
    *,
    auth_dir=None,
    post_token=None,
) -> tuple[str, dict | None]:
    mode = (auth_mode or AUTH_AUTO).strip().lower() or AUTH_AUTO
    if mode not in AUTH_MODES:
        raise RequestError(f"Unknown auth mode: {auth_mode}")
    supports = model_supports_codex_oauth(model)
    if mode == AUTH_API_KEY:
        return AUTH_API_KEY, None
    if mode == AUTH_OAUTH:
        if not supports:
            raise RequestError(
                f"{model.model_id} does not support ChatGPT OAuth. "
                "Use --model gpt-5.6-terra or --auth api_key."
            )
        tokens = load_fresh_openai_tokens(auth_dir, post_token=post_token)
        if not tokens:
            raise RequestError(
                "Not logged in. Run: python manage.py auth_login --provider openai"
            )
        return AUTH_OAUTH, tokens
    if supports:
        tokens = load_fresh_openai_tokens(auth_dir, post_token=post_token)
        if tokens:
            return AUTH_OAUTH, tokens
    return AUTH_API_KEY, None


def estimate_cost(model: LLMModel, input_tokens: int, output_tokens: int) -> str | None:
    if model.input_cost_per_1m is None or model.output_cost_per_1m is None:
        return None
    million = Decimal("1000000")
    cost = (
        Decimal(input_tokens) / million * model.input_cost_per_1m
        + Decimal(output_tokens) / million * model.output_cost_per_1m
    )
    return str(cost.quantize(Decimal("0.000001")))


def complete_single_turn(
    prompt: str,
    model_id: str | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    system: str | None = None,
    openai_client=None,
    auth_mode: str | None = None,
    auth_dir=None,
    post_token=None,
) -> dict:
    if not (prompt or "").strip():
        raise RequestError("prompt is required.")

    model, warnings = resolve_model(model_id)
    cap = model.max_output_tokens
    tokens = max_output_tokens
    if tokens is None:
        tokens = cap or DEFAULT_MAX_OUTPUT_TOKENS
    if cap is not None and tokens > cap:
        raise RequestError(
            f"max_output_tokens {tokens} exceeds model cap {cap} for {model.model_id}."
        )
    if tokens < 1:
        raise RequestError("max_output_tokens must be >= 1.")

    temp = temperature
    if temp is None:
        temp = model.default_temperature if model.default_temperature is not None else 1.0

    resolved_auth, oauth_tokens = resolve_auth_mode(
        model, auth_mode, auth_dir=auth_dir, post_token=post_token
    )

    if openai_client is not None:
        client = openai_client
    elif resolved_auth == AUTH_OAUTH:
        client = _codex_client(
            oauth_tokens["access_token"], oauth_tokens["account_id"]
        )
    else:
        client = _openai_client()

    use_oauth_kwargs = resolved_auth == AUTH_OAUTH
    try:
        if model.endpoint_kind == LLMModel.EndpointKind.RESPONSES:
            text, input_tokens, output_tokens = _complete_via_responses(
                client,
                model.model_id,
                prompt,
                tokens,
                temp,
                system,
                oauth=use_oauth_kwargs,
            )
        else:
            text, input_tokens, output_tokens = _complete_via_chat(
                client, model.model_id, prompt, tokens, temp, system
            )
    except Exception as exc:
        retried = _retry_oauth_after_unauthorized(
            exc,
            openai_client=openai_client,
            resolved_auth=resolved_auth,
            auth_dir=auth_dir,
            post_token=post_token,
        )
        if retried is None:
            _reraise_openai_error(exc)
        client = retried
        if model.endpoint_kind == LLMModel.EndpointKind.RESPONSES:
            text, input_tokens, output_tokens = _complete_via_responses(
                client,
                model.model_id,
                prompt,
                tokens,
                temp,
                system,
                oauth=use_oauth_kwargs,
            )
        else:
            text, input_tokens, output_tokens = _complete_via_chat(
                client, model.model_id, prompt, tokens, temp, system
            )

    estimated = None
    if resolved_auth != AUTH_OAUTH:
        estimated = estimate_cost(model, input_tokens, output_tokens)

    return {
        "text": text or "",
        "model_id": model.model_id,
        "endpoint_kind": model.endpoint_kind,
        "auth_mode": resolved_auth,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
        "estimated_cost_usd": estimated,
        "warnings": warnings,
    }


def _is_unauthorized(exc) -> bool:
    status = getattr(exc, "status_code", None)
    return status == 401


def _retry_oauth_after_unauthorized(
    exc,
    *,
    openai_client,
    resolved_auth,
    auth_dir,
    post_token,
):
    if openai_client is not None or resolved_auth != AUTH_OAUTH:
        return None
    if not _is_unauthorized(exc):
        return None
    tokens = load_fresh_openai_tokens(
        auth_dir, post_token=post_token, force_refresh=True
    )
    if not tokens:
        raise RequestError(
            "Not logged in. Run: python manage.py auth_login --provider openai"
        )
    return _codex_client(tokens["access_token"], tokens["account_id"])


def _reraise_openai_error(exc):
    status = getattr(exc, "status_code", None)
    message = str(exc)
    if status:
        raise RequestError(f"OpenAI request failed ({status}): {message}") from exc
    raise exc


def _complete_via_chat(client, model_id, prompt, max_output_tokens, temperature, system):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model=model_id,
        messages=messages,
        max_tokens=max_output_tokens,
        temperature=temperature,
    )
    choice = response.choices[0]
    text = getattr(choice.message, "content", None) or ""
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    return text, input_tokens, output_tokens


def _complete_via_responses(
    client, model_id, prompt, max_output_tokens, temperature, system, oauth=False
):
    kwargs = {
        "model": model_id,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
    }
    if system:
        kwargs["instructions"] = system
    if oauth:
        kwargs["store"] = False
    response = client.responses.create(**kwargs)
    text = getattr(response, "output_text", None) or ""
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None)
    if input_tokens is None:
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", None)
    if output_tokens is None:
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
    return text, input_tokens, output_tokens
