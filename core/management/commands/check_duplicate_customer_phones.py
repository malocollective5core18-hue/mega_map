from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from core.models import CustomerBusiness


class Command(BaseCommand):
    help = "Read-only pre-migration check for customer phone duplicates."

    def handle(self, *args, **options):
        duplicates = list(
            CustomerBusiness.objects.values("phone")
            .annotate(record_count=Count("pk"))
            .filter(record_count__gt=1)
            .order_by("phone")
        )
        if not duplicates:
            self.stdout.write(self.style.SUCCESS("No duplicate customer phones found."))
            return

        self.stderr.write(
            "Duplicate customer phones found; stop before applying a phone uniqueness migration:"
        )
        for row in duplicates:
            phone = row["phone"]
            self.stderr.write(f"  •••• {phone[-4:]}: {row['record_count']} records")
        raise CommandError("Resolve duplicate customer phone records before migrating.")
