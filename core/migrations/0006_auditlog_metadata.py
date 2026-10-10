from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_providercode_reusable"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
