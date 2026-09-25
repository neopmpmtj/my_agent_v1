from request.cli_output import dumps, list_envelope
from request.management.command_utils import JsonCommand
from request.services import list_llm_models, serialize_llm_model


class Command(JsonCommand):
    help = "List catalogued LLM models. Use --json for machine-readable output."

    def add_arguments(self, parser):
        self.add_json_argument(parser)
        parser.add_argument(
            "--all",
            action="store_true",
            help="Include inactive models.",
        )

    def handle(self, *args, **options):
        models = list_llm_models(active_only=not options["all"])
        items = [serialize_llm_model(obj) for obj in models]
        kinds = sorted({item["endpoint_kind"] for item in items})
        extra = {"endpoint_kinds_in_catalog": kinds} if kinds else {}
        if options["json"]:
            self.stdout.write(dumps(list_envelope("llm_model", items, extra=extra)))
            return
        if not items:
            self.stdout.write("No models. Run: python manage.py model_sync")
            return
        self.stdout.write(
            f"{'model_id':<24} {'endpoint':<18} {'in/1M':>8} {'out/1M':>8}  flags"
        )
        for item in items:
            flags = []
            if item["is_default"]:
                flags.append("default")
            if not item["is_active"]:
                flags.append("inactive")
            in_cost = item["input_cost_per_1m"]
            out_cost = item["output_cost_per_1m"]
            self.stdout.write(
                f"{item['model_id']:<24} {item['endpoint_kind']:<18} "
                f"{str(in_cost or '-'):>8} {str(out_cost or '-'):>8}  "
                f"{','.join(flags) or '-'}"
            )
        if len(kinds) > 1:
            self.stderr.write("Mixed endpoint kinds: " + ", ".join(kinds))
