from types import SimpleNamespace

from request.models import LLMModel


class FakeModels:
    def __init__(self, ids):
        self._ids = ids

    def list(self):
        return [SimpleNamespace(id=model_id) for model_id in self._ids]


class FakeChatCompletions:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.chat_calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="sky is blue"))],
            usage=SimpleNamespace(prompt_tokens=8, completion_tokens=4),
        )


class FakeResponses:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.response_calls.append(kwargs)
        return SimpleNamespace(
            output_text="via responses",
            usage=SimpleNamespace(input_tokens=10, output_tokens=6),
        )


class FakeOpenAIClient:
    def __init__(self, ids):
        self.models = FakeModels(ids)
        self.chat_calls = []
        self.response_calls = []
        self.chat = SimpleNamespace(completions=FakeChatCompletions(self))
        self.responses = FakeResponses(self)


def make_model(**overrides):
    defaults = {
        "provider": "openai",
        "model_id": "gpt-4o-mini",
        "display_name": "GPT-4o mini",
        "endpoint_kind": LLMModel.EndpointKind.CHAT_COMPLETIONS,
        "input_cost_per_1m": "0.15",
        "output_cost_per_1m": "0.60",
        "max_output_tokens": 16384,
        "default_temperature": 1.0,
        "is_default": True,
        "is_active": True,
    }
    defaults.update(overrides)
    return LLMModel.objects.create(**defaults)
