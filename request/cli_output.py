import json
from datetime import date, datetime
from decimal import Decimal


def dumps(payload):
    return json.dumps(payload, ensure_ascii=False, default=_json_default)


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def list_envelope(entity, items, extra=None):
    payload = {
        "ok": True,
        "entity": entity,
        "count": len(items),
        "items": items,
    }
    if extra:
        payload.update(extra)
    return payload


def error_envelope(message):
    return {"ok": False, "error": message}


def ok_envelope(**kwargs):
    payload = {"ok": True}
    payload.update(kwargs)
    return payload
