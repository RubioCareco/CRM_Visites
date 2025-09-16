from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('front', '0012_drop_legacy_import_tables'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                SET FOREIGN_KEY_CHECKS = 0;
                DROP TABLE IF EXISTS `front_client_backup_20250822`;
                SET FOREIGN_KEY_CHECKS = 1;
            """,
            reverse_sql="""
                -- Pas de recréation pour une table de backup
            """,
        ),
    ]


