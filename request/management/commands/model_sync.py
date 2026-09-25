from request.cli_output import dumps, ok_envelope
from request.management.command_utils import JsonCommand
from request.services import RequestError, sync_model_catalog


class Command(JsonCommand):
    help = "Merge curated openai_models.json with OpenAI models.list into the DB."

    def add_arguments(self, parser):
        self.add_json_argument(parser)

    def handle(self, *args, **options):
        as_json = options["json"]
        try:
            result = sync_model_catalog()
        except RequestError as exc:
            self.fail(str(exc), as_json)
        if as_json:
            self.stdout.write(dumps(ok_envelope(**result)))
            return
        self.stdout.write(
            f"added={result['added']} updated={result['updated']} "
            f"api={result['api_count']} curated={result['curated_count']}"
        )
        for warning in result["warnings"]:
            self.stderr.write(warning)
