from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_staffmfafailure_staffmfarecoverycode"),
    ]

    operations = [
        migrations.AddField(
            model_name="businesslocation",
            name="fix_age_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="businesslocation",
            name="pin_offset_m",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="businesslocation",
            name="pin_moved_by_hand",
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name="businesslocation",
            constraint=models.CheckConstraint(
                condition=models.Q(pin_offset_m__isnull=True) | models.Q(pin_offset_m__gte=0),
                name="business_pin_offset_nonnegative",
            ),
        ),
    ]
