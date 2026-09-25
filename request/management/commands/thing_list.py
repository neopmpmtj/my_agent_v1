import json

from django.core.management.base import BaseCommand

from request.services import list_things


class Command(BaseCommand):
    help = "List things (stub). Use --json for agent-friendly stdout."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print a JSON envelope on stdout.",
        )

    def handle(self, *args, **options):
        items = list_things()
        if options["json"]:
            payload = {
                "ok": True,
                "entity": "thing",
                "count": len(items),
                "items": items,
            }
            self.stdout.write(json.dumps(payload, ensure_ascii=False))
            return

        if not items:
            self.stdout.write("No things.")
            return

        for row in items:
            self.stdout.write(str(row))
