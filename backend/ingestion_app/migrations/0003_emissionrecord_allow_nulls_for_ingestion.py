from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingestion_app", "0002_emissionrecord_raw_unit_default"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emissionrecord",
            name="raw_value",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="emissionrecord",
            name="normalized_value",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
        migrations.AlterField(
            model_name="emissionrecord",
            name="normalized_unit",
            field=models.CharField(blank=True, default="unknown", max_length=50),
        ),
        migrations.AlterField(
            model_name="emissionrecord",
            name="activity_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]

