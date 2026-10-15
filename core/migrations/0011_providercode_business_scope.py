import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_customerflagcase"),
    ]

    operations = [
        migrations.AddField(
            model_name="providercode",
            name="business",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="provider_codes",
                to="core.customerbusiness",
            ),
        ),
        migrations.AddField(
            model_name="providercode",
            name="legacy_phone_lookup",
            field=models.BooleanField(default=True),
        ),
    ]
