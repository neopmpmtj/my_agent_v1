from request.cli_output import dumps, ok_envelope
from request.management.command_utils import JsonCommand
from request.services import RequestError, remove_model_from_stack


class Command(JsonCommand):
    help = (
        "Remove a model from openai_models.json (deactivate on llm_ask), "
        "then run model_sync."
    )

    def add_arguments(self, parser):
        self.add_json_argument(parser)
        parser.add_argument("--model", required=True, help="API model id.")

    def handle(self, *args, **options):
        as_json = options["json"]
        try:
            result = remove_model_from_stack(options["model"])
        except RequestError as exc:
            self.fail(str(exc), as_json)
        if as_json:
            self.stdout.write(dumps(ok_envelope(**result)))
            return
        self.stdout.write(f"removed {result['model_id']}")
        if result.get("new_default_id"):
            self.stdout.write(f"new default: {result['new_default_id']}")
        for warning in result["warnings"]:
            self.stderr.write(warning)
