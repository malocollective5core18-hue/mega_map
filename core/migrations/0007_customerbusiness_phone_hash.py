import hashlib
import hmac

from django.conf import settings
from django.db import migrations, models


def populate_phone_hashes(apps, schema_editor):
    if not settings.SECRET_KEY:
        raise RuntimeError("DJANGO_SECRET_KEY is required to populate customer phone hashes.")
    Business = apps.get_model("core", "CustomerBusiness")
    key = settings.SECRET_KEY.encode()
    alias = schema_editor.connection.alias
    batch = []
    for business in Business.objects.using(alias).only("pk", "phone").iterator(chunk_size=500):
        business.phone_hash = hmac.new(
            key, ("provider-phone:" + business.phone).encode(), hashlib.sha256
        ).hexdigest()
        batch.append(business)
        if len(batch) >= 500:
            Business.objects.using(alias).bulk_update(batch, ["phone_hash"], batch_size=500)
            batch.clear()
    if batch:
        Business.objects.using(alias).bulk_update(batch, ["phone_hash"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("core", "0006_auditlog_metadata")]

    operations = [
        migrations.AddField(
            model_name="customerbusiness",
            name="phone_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.RunPython(populate_phone_hashes, migrations.RunPython.noop),
    ]
