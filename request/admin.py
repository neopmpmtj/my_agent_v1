from django.contrib import admin

from request.models import LLMModel


@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = (
        "model_id",
        "provider",
        "endpoint_kind",
        "is_default",
        "is_active",
        "input_cost_per_1m",
        "output_cost_per_1m",
    )
    list_filter = ("provider", "endpoint_kind", "is_active", "is_default")
    search_fields = ("model_id", "display_name")
