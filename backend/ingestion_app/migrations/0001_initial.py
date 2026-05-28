from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("company_name", models.CharField(max_length=255, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "tenant",
            },
        ),
        migrations.CreateModel(
            name="DataSource",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="ingestion_app.tenant"
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("sap", "SAP (Fuel & Procurement)"),
                            ("utility", "Utility (Electricity)"),
                            ("travel", "Corporate Travel"),
                        ],
                        max_length=20,
                    ),
                ),
                ("uploaded_by", models.CharField(max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("original_filename", models.CharField(max_length=255)),
                ("file_hash", models.CharField(max_length=64, unique=True)),
                ("row_count", models.IntegerField(default=0)),
                (
                    "processing_status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="uploaded",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True, null=True)),
            ],
            options={
                "db_table": "data_source",
                "ordering": ["-uploaded_at"],
            },
        ),
        migrations.CreateModel(
            name="EmissionRecord",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="ingestion_app.tenant"
                    ),
                ),
                (
                    "data_source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="ingestion_app.datasource",
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("1", "Scope 1 (Direct)"),
                            ("2", "Scope 2 (Energy)"),
                            ("3", "Scope 3 (Other Indirect)"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        max_length=20,
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("fuel", "Fuel (Vehicles)"),
                            ("electricity", "Electricity"),
                            ("travel_flight", "Flight Travel"),
                            ("travel_hotel", "Hotel Stay"),
                            ("travel_ground", "Ground Transport"),
                            ("procurement", "Procurement"),
                            ("natural_gas", "Natural Gas"),
                            ("other", "Other"),
                        ],
                        max_length=50,
                    ),
                ),
                ("activity_type", models.CharField(max_length=255)),
                ("raw_value", models.CharField(max_length=255)),
                ("raw_unit", models.CharField(blank=True, max_length=50)),
                ("normalized_value", models.DecimalField(decimal_places=4, max_digits=15)),
                ("normalized_unit", models.CharField(max_length=50)),
                ("activity_date", models.DateField()),
                ("plant_code", models.CharField(blank=True, max_length=50)),
                ("employee_name", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Review"),
                            ("flagged", "Flagged - Issues Detected"),
                            ("approved", "Approved"),
                            ("locked", "Locked for Audit"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("suspicious_flag", models.BooleanField(default=False)),
                ("confidence_score", models.IntegerField(default=100)),
                ("locked_for_audit", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "emission_record",
                "ordering": ["-activity_date"],
            },
        ),
        migrations.CreateModel(
            name="ValidationIssue",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="issues",
                        to="ingestion_app.emissionrecord",
                    ),
                ),
                (
                    "issue_type",
                    models.CharField(
                        choices=[
                            ("negative_value", "Negative Value"),
                            ("missing_date", "Missing Activity Date"),
                            ("invalid_unit", "Invalid/Unknown Unit"),
                            ("duplicate_row", "Potential Duplicate"),
                            ("outlier_high", "Value Unusually High"),
                            ("outlier_low", "Value Unusually Low"),
                            ("missing_context", "Missing Context (plant, employee)"),
                            ("invalid_date_format", "Invalid Date Format"),
                            ("zero_value", "Zero Value"),
                            ("other", "Other"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("error", "Error - Blocks Approval"),
                            ("warning", "Warning - Needs Review"),
                            ("info", "Info - FYI"),
                        ],
                        max_length=20,
                    ),
                ),
                ("description", models.TextField()),
                ("resolved", models.BooleanField(default=False)),
                ("resolution_notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "validation_issue",
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="audit_logs",
                        to="ingestion_app.emissionrecord",
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("created", "Record Created"),
                            ("updated", "Record Updated"),
                            ("approved", "Record Approved"),
                            ("locked", "Record Locked"),
                            ("issue_flagged", "Issue Flagged"),
                            ("issue_resolved", "Issue Resolved"),
                        ],
                        max_length=50,
                    ),
                ),
                ("changed_by", models.CharField(max_length=255)),
                ("field_name", models.CharField(blank=True, max_length=100)),
                ("old_value", models.TextField(blank=True)),
                ("new_value", models.TextField(blank=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "audit_log",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="emissionrecord",
            index=models.Index(fields=["tenant", "status"], name="emission_rec_tenant__a09a10_idx"),
        ),
        migrations.AddIndex(
            model_name="emissionrecord",
            index=models.Index(fields=["tenant", "created_at"], name="emission_rec_tenant__5a6444_idx"),
        ),
        migrations.AddIndex(
            model_name="emissionrecord",
            index=models.Index(fields=["data_source"], name="emission_rec_data_so_8e2e72_idx"),
        ),
    ]

