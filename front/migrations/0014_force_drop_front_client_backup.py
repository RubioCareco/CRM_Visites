from django.db import migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('front', '0013_drop_front_client_backup_table'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                SET FOREIGN_KEY_CHECKS = 0;
                DROP TABLE IF EXISTS `crm_visites`.`front_client_backup_20250822`;
                DROP TABLE IF EXISTS `front_client_backup_20250822`;
                SET FOREIGN_KEY_CHECKS = 1;
            """,
            reverse_sql="""
                -- No reverse operation
            """,
        ),
    ]


