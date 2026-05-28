from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingestion_app", "0003_emissionrecord_allow_nulls_for_ingestion"),
    ]

    operations = [
        migrations.AlterField(
            model_name="datasource",
            name="file_hash",
            field=models.CharField(max_length=64),
        ),
    ]

