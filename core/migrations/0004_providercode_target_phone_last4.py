from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_providercode_target_phone_hash"),
    ]

    operations = [
        migrations.AddField(
            model_name="providercode",
            name="target_phone_last4",
            field=models.CharField(blank=True, default="", max_length=4),
        ),
    ]
