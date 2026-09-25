from request.cli_output import dumps, ok_envelope
from request.management.command_utils import JsonCommand
from request.services import RequestError, auth_login


class Command(JsonCommand):
    help = (
        "Sign in with ChatGPT (Codex OAuth) for subscription inference. "
        "v1 implements --provider openai only."
    )

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
            result = auth_login(
                options["provider"],
                announce_url=lambda url: self.stderr.write(
                    "Open this URL if the browser does not open:\n" + url
                ),
            )
        except RequestError as exc:
            self.fail(str(exc), as_json)
        if as_json:
            self.stdout.write(dumps(ok_envelope(**result)))
            return
        plan = result.get("plan_type") or "-"
        self.stdout.write(
            f"logged in provider={result['provider']} plan={plan}"
        )
