from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingestion_app", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emissionrecord",
            name="raw_unit",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
    ]

