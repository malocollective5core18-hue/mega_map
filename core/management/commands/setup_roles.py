from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the standard staff role groups required by the dashboard."

    def handle(self, *args, **options):
        for name in ("dispatcher", "admin"):
            Group.objects.get_or_create(name=name)
            self.stdout.write(f"Ensured role group: {name}")
