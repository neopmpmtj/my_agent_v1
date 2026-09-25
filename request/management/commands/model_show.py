from request.cli_output import dumps, ok_envelope
from request.management.command_utils import JsonCommand
from request.services import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    RequestError,
    get_llm_model,
    serialize_llm_model,
)


class Command(JsonCommand):
    help = "Show one catalogued LLM model."

    def add_arguments(self, parser):
        self.add_json_argument(parser)
        parser.add_argument("--model", required=True, help="API model id.")

    def handle(self, *args, **options):
        as_json = options["json"]
        try:
            obj = get_llm_model(options["model"])
        except RequestError as exc:
            self.fail(str(exc), as_json)
        row = serialize_llm_model(obj)
        defaults = {
            "max_output_tokens": obj.max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS,
            "temperature": obj.default_temperature
            if obj.default_temperature is not None
            else 1.0,
        }
        if as_json:
            self.stdout.write(dumps(ok_envelope(model=row, cli_defaults=defaults)))
            return
        self.stdout.write(f"{obj.model_id} ({obj.display_name})")
        self.stdout.write(f"  endpoint_kind: {obj.endpoint_kind}")
        self.stdout.write(f"  input_cost_per_1m: {obj.input_cost_per_1m}")
        self.stdout.write(f"  output_cost_per_1m: {obj.output_cost_per_1m}")
        self.stdout.write(f"  max_output_tokens: {obj.max_output_tokens}")
        self.stdout.write(f"  is_default: {obj.is_default}")
        self.stdout.write(f"  is_active: {obj.is_active}")
        if obj.catalog_notes:
            self.stdout.write(f"  notes: {obj.catalog_notes}")
        self.stdout.write(
            f"  cli defaults: max_output_tokens={defaults['max_output_tokens']} "
            f"temperature={defaults['temperature']}"
        )
