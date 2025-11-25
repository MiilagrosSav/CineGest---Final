from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0012_add_cupon_utilizado'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE \"ventas_historicalventa\" "
                "ADD COLUMN IF NOT EXISTS \"cupon_utilizado_id\" integer;"
            ),
            reverse_sql=(
                "ALTER TABLE \"ventas_historicalventa\" "
                "DROP COLUMN IF EXISTS \"cupon_utilizado_id\";"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS "
                "ventas_historicalventa_cupon_utilizado_id_idx "
                "ON \"ventas_historicalventa\" (\"cupon_utilizado_id\");"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS ventas_historicalventa_cupon_utilizado_id_idx;"
            ),
        ),
    ]
