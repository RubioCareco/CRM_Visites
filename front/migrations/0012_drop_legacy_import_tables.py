from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('front', '0011_add_client_visit_stats'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DROP TABLE IF EXISTS import_clients_corrected;
                DROP TABLE IF EXISTS font_client_backup_20250822;
            """,
            reverse_sql="""
                -- Pas de recréation automatique pour des tables legacy
            """,
        ),
    ]


