import json

from django.core.management import call_command
from io import StringIO

import pytest


@pytest.mark.integration
def test_thing_list_json_empty():
    out = StringIO()
    call_command("thing_list", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload == {"ok": True, "entity": "thing", "count": 0, "items": []}


@pytest.mark.integration
def test_thing_list_human_empty(capsys):
    call_command("thing_list")
    captured = capsys.readouterr()
    assert captured.out.strip() == "No things."
