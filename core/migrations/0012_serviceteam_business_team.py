import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0011_providercode_business_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceTeam",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("leader", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="led_service_teams", to=settings.AUTH_USER_MODEL)),
                ("members", models.ManyToManyField(blank=True, related_name="service_teams", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="customerbusiness",
            name="assigned_team",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_businesses", to="core.serviceteam"),
        ),
    ]
