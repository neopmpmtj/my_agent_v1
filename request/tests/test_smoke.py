from django.test import Client
from django.conf import settings


def test_openai_settings_present():
    assert hasattr(settings, "OPENAI_API_KEY")
    assert hasattr(settings, "OPENAI_MODEL")
    assert settings.OPENAI_MODEL


def test_health_endpoint():
    client = Client()
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
