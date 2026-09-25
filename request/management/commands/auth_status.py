from request.cli_output import dumps, ok_envelope
from request.management.command_utils import JsonCommand
from request.services import RequestError, auth_status


class Command(JsonCommand):
    help = "Show ChatGPT/Codex OAuth status. Never prints tokens."

    def add_arguments(self, parser):
        self.add_json_argument(parser)
        parser.add_argument(
            "--provider",
            default="openai",
            help="Auth provider (default: openai).",
        )

    def handle(self, *args, **options):
        as_json = options["json"]
        try:
            result = auth_status(options["provider"])
        except RequestError as exc:
            self.fail(str(exc), as_json)
        if as_json:
            self.stdout.write(dumps(ok_envelope(**result)))
            return
        if not result["logged_in"]:
            self.stdout.write(f"{result['provider']}: not logged in")
            return
        plan = result.get("plan_type") or "-"
        expired = "expired" if result["expired"] else "ok"
        self.stdout.write(
            f"{result['provider']}: logged in plan={plan} token={expired}"
        )
