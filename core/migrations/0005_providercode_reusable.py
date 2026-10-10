from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_providercode_target_phone_last4"),
    ]

    operations = [
        migrations.AddField(
            model_name="providercode",
            name="reusable",
            field=models.BooleanField(default=False),
        ),
    ]
