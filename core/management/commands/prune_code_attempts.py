from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import CodeAttempt


class Command(BaseCommand):
    help = "Delete expired provider-code attempt digests."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24, help="Delete attempts older than this many hours.")
        parser.add_argument("--batch-size", type=int, default=1000, help="Maximum rows deleted per query.")

    def handle(self, *args, **options):
        hours = options["hours"]
        batch_size = options["batch_size"]
        if hours < 1:
            raise CommandError("--hours must be at least 1.")
        if not 1 <= batch_size <= 10_000:
            raise CommandError("--batch-size must be between 1 and 10000.")

        cutoff = timezone.now() - timedelta(hours=hours)
        total = 0
        while True:
            stale_ids = list(
                CodeAttempt.objects.filter(created_at__lt=cutoff)
                .order_by("created_at")
                .values_list("pk", flat=True)[:batch_size]
            )
            if not stale_ids:
                break
            deleted, _ = CodeAttempt.objects.filter(pk__in=stale_ids).delete()
            total += deleted

        self.stdout.write(f"Pruned {total} expired code-attempt rows older than {hours} hours.")
