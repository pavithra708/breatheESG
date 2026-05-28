"""
Compatibility shim.

The Django app for this project is `ingestion_app` (see `backend/settings.py`).
Historically, models lived in `backend/models.py` and were imported as
`from models import ...`, which breaks Django's app registry because those models
end up belonging to the non-app module `models`.

This file intentionally re-exports models from `ingestion_app.models` so any
legacy imports keep working, while Django only registers models from the
installed app.
"""

from ingestion_app.models import *  # noqa: F403

from ingestion_app.models import (  # noqa: F401
    AuditLog,
    Category,
    DataSource,
    EmissionRecord,
    RecordStatus,
    Scope,
    SourceType,
    Tenant,
    ValidationIssue,
)

__all__ = [
    "Tenant",
    "SourceType",
    "DataSource",
    "Scope",
    "Category",
    "RecordStatus",
    "EmissionRecord",
    "ValidationIssue",
    "AuditLog",
]
