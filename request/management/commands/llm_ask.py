from request.cli_output import dumps, ok_envelope
from request.management.command_utils import JsonCommand
from request.services import RequestError, complete_single_turn


class Command(JsonCommand):
    help = "Single-turn LLM request: one prompt in, one assistant reply out."

    def add_arguments(self, parser):
        self.add_json_argument(parser)
        parser.add_argument("--prompt", required=True, help="User prompt.")
        parser.add_argument("--model", default="", help="API model id (default: catalog).")
        parser.add_argument(
            "--max-output-tokens",
            type=int,
            default=None,
            help="Cap on generated tokens.",
        )
        parser.add_argument("--temperature", type=float, default=None)
        parser.add_argument("--system", default="", help="Optional system message.")
        parser.add_argument(
            "--auth",
            default="auto",
            help="auto (default), oauth, or api_key.",
        )

    def handle(self, *args, **options):
        as_json = options["json"]
        try:
            result = complete_single_turn(
                prompt=options["prompt"],
                model_id=options["model"] or None,
                max_output_tokens=options["max_output_tokens"],
                temperature=options["temperature"],
                system=options["system"] or None,
                auth_mode=options["auth"],
            )
        except RequestError as exc:
            self.fail(str(exc), as_json)
        if as_json:
            payload = ok_envelope(
                text=result["text"],
                model_id=result["model_id"],
                endpoint_kind=result["endpoint_kind"],
                auth_mode=result["auth_mode"],
                usage=result["usage"],
                estimated_cost_usd=result["estimated_cost_usd"],
            )
            if result["warnings"]:
                payload["warnings"] = result["warnings"]
            self.stdout.write(dumps(payload))
            return
        for warning in result["warnings"]:
            self.stderr.write(warning)
        self.stdout.write(result["text"])
