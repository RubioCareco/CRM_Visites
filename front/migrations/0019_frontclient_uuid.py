import uuid

from django.db import migrations, models


def _backfill_frontclient_uuid(apps, schema_editor):
    FrontClient = apps.get_model("front", "FrontClient")
    for client in FrontClient.objects.filter(uuid__isnull=True).iterator(chunk_size=500):
        client.uuid = uuid.uuid4()
        client.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    dependencies = [
        ("front", "0018_activitylog_actor_commercial_activitylog_actor_role_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="frontclient",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(_backfill_frontclient_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="frontclient",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
