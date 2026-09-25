import sys

from django.core.management.base import BaseCommand, CommandError

from request.cli_output import dumps, error_envelope


class JsonCommand(BaseCommand):
    def add_json_argument(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print a JSON envelope on stdout.",
        )

    def fail(self, message, as_json):
        if as_json:
            self.stdout.write(dumps(error_envelope(message)))
            sys.exit(1)
        raise CommandError(message)
