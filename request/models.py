from django.db import models


class LLMModel(models.Model):
    class EndpointKind(models.TextChoices):
        CHAT_COMPLETIONS = "chat_completions", "Chat completions"
        RESPONSES = "responses", "Responses"

    provider = models.CharField(max_length=32, default="openai")
    model_id = models.CharField(max_length=128)
    display_name = models.CharField(max_length=128)
    endpoint_kind = models.CharField(max_length=32, choices=EndpointKind.choices)
    input_cost_per_1m = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )
    output_cost_per_1m = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )
    max_input_tokens = models.PositiveIntegerField(null=True, blank=True)
    max_output_tokens = models.PositiveIntegerField(null=True, blank=True)
    default_temperature = models.FloatField(null=True, blank=True)
    supports_json_mode = models.BooleanField(default=False)
    is_agent_capable = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    api_seen_at = models.DateTimeField(null=True, blank=True)
    catalog_notes = models.TextField(blank=True, default="")
    extra_params = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "model_id"],
                name="uniq_provider_model_id",
            ),
        ]
        ordering = ["provider", "model_id"]

    def __str__(self):
        return f"{self.provider}:{self.model_id}"
