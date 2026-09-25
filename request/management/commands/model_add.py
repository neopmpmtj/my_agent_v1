from request.cli_output import dumps, ok_envelope
from request.management.command_utils import JsonCommand
from request.services import RequestError, add_model_to_stack


class Command(JsonCommand):
    help = (
        "Add a model to openai_models.json (LiteLLM prices or explicit costs), "
        "then run model_sync."
    )

    def add_arguments(self, parser):
        self.add_json_argument(parser)
        parser.add_argument("--model", required=True, help="API model id.")
        parser.add_argument(
            "--default",
            action="store_true",
            help="Make this the default model for llm_ask.",
        )
        parser.add_argument("--input-cost-per-1m", default=None)
        parser.add_argument("--output-cost-per-1m", default=None)
        parser.add_argument(
            "--endpoint-kind",
            default=None,
            help="chat_completions or responses (default: heuristic).",
        )

    def handle(self, *args, **options):
        as_json = options["json"]
        try:
            result = add_model_to_stack(
                options["model"],
                input_cost_per_1m=options["input_cost_per_1m"],
                output_cost_per_1m=options["output_cost_per_1m"],
                endpoint_kind=options["endpoint_kind"],
                is_default=options["default"],
            )
        except RequestError as exc:
            self.fail(str(exc), as_json)
        if as_json:
            self.stdout.write(dumps(ok_envelope(**result)))
            return
        self.stdout.write(
            f"added {result['model_id']} "
            f"in={result['input_cost_per_1m']} out={result['output_cost_per_1m']} "
            f"endpoint={result['endpoint_kind']}"
        )
        for warning in result["warnings"]:
            self.stderr.write(warning)
