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
    for business in Business.objects.using(alias).only("pk", "phone").iterator(chunk_size=500):
        digest = hmac.new(key, ("provider-phone:" + business.phone).encode(), hashlib.sha256).hexdigest()
        Business.objects.using(alias).filter(pk=business.pk).update(phone_hash=digest)


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
