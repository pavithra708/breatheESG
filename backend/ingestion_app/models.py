"""
Core data models for ESG data ingestion platform.

The model design prioritizes:
1. Source-of-truth tracking (which system produced this data)
2. Audit trail (who changed what, when)
3. Immutable locked state (for audit compliance)
4. Scope categorization (Scope 1/2/3)
5. Multi-tenancy (multiple clients on same platform)
"""

from django.db import models
from django.utils import timezone
from enum import Enum


class Tenant(models.Model):
    """
    Multi-tenant support. Each company is a separate tenant.
    
    Why multi-tenancy:
    - Real enterprise systems serve multiple clients
    - Data isolation is critical for compliance
    - Billing often per-tenant
    """
    id = models.AutoField(primary_key=True)
    company_name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'tenant'
    
    def __str__(self):
        return self.company_name


class SourceType(models.TextChoices):
    """
    The three source types we handle.
    """
    SAP = 'sap', 'SAP (Fuel & Procurement)'
    UTILITY = 'utility', 'Utility (Electricity)'
    TRAVEL = 'travel', 'Corporate Travel'


class DataSource(models.Model):
    """
    Tracks where data came from. Critical for audit trail.
    
    Why this model:
    - Links raw upload to processed records
    - Enables batch reprocessing
    - Provides source lineage (which upload produced which records)
    - Supports rejection of entire uploads if needed
    """
    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    uploaded_by = models.CharField(max_length=255)  # email/username
    uploaded_at = models.DateTimeField(auto_now_add=True)
    original_filename = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)  # SHA256 of file (dedupe handled at API layer)
    row_count = models.IntegerField(default=0)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('uploaded', 'Uploaded'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='uploaded'
    )
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'data_source'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.get_source_type_display()} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"


class Scope(models.TextChoices):
    """
    GHG Protocol scopes.
    
    Scope 1: Direct emissions (company-owned vehicles, facilities)
    Scope 2: Indirect energy (purchased electricity, steam)
    Scope 3: All other indirect (travel, commuting, supply chain)
    """
    SCOPE_1 = '1', 'Scope 1 (Direct)'
    SCOPE_2 = '2', 'Scope 2 (Energy)'
    SCOPE_3 = '3', 'Scope 3 (Other Indirect)'
    UNKNOWN = 'unknown', 'Unknown'


class Category(models.TextChoices):
    """
    Activity categories across all sources.
    """
    FUEL = 'fuel', 'Fuel (Vehicles)'
    ELECTRICITY = 'electricity', 'Electricity'
    TRAVEL_FLIGHT = 'travel_flight', 'Flight Travel'
    TRAVEL_HOTEL = 'travel_hotel', 'Hotel Stay'
    TRAVEL_GROUND = 'travel_ground', 'Ground Transport'
    PROCUREMENT = 'procurement', 'Procurement'
    NATURAL_GAS = 'natural_gas', 'Natural Gas'
    OTHER = 'other', 'Other'


class RecordStatus(models.TextChoices):
    """
    Workflow status of a record.
    
    This is critical for analyst approval workflow:
    - PENDING: Uploaded, awaiting review
    - FLAGGED: Has validation issues, needs correction
    - APPROVED: Analyst approved, can be locked
    - LOCKED: Locked for audit, immutable
    """
    PENDING = 'pending', 'Pending Review'
    FLAGGED = 'flagged', 'Flagged - Issues Detected'
    APPROVED = 'approved', 'Approved'
    LOCKED = 'locked', 'Locked for Audit'


class EmissionRecord(models.Model):
    """
    CORE MODEL: Unified normalized emission record.
    
    Why single normalized model:
    - All data (SAP, utility, travel) normalized into same schema
    - Simplifies validation rules
    - Simplifies downstream computation
    - Makes analyst dashboard simple
    
    Fields explained:
    - raw_value: Original value before normalization
    - normalized_value: Standardized numeric value
    - normalized_unit: Standard unit (e.g., always "kg" for fuel)
    - activity_date: When activity occurred (not when uploaded)
    - source_tracking: Links back to DataSource for lineage
    - suspicious_flag: Whether validation detected anomalies
    - locked_for_audit: Immutable once locked (compliance requirement)
    """
    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE)
    
    # Activity classification
    scope = models.CharField(max_length=20, choices=Scope.choices, default='unknown')
    category = models.CharField(max_length=50, choices=Category.choices)
    activity_type = models.CharField(max_length=255)  # More granular (e.g., "Diesel Fuel")
    
    # Raw data
    raw_value = models.CharField(max_length=255, blank=True, default="")  # Original string value
    raw_unit = models.CharField(max_length=50, blank=True, default="")
    
    # Normalized data
    normalized_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    normalized_unit = models.CharField(max_length=50, blank=True, default="unknown")  # Always standardized
    
    # Contextual data
    activity_date = models.DateField(null=True, blank=True)  # When activity occurred
    plant_code = models.CharField(max_length=50, blank=True)
    employee_name = models.CharField(max_length=255, blank=True)
    
    # Workflow state
    status = models.CharField(
        max_length=20,
        choices=RecordStatus.choices,
        default='pending'
    )
    
    # Quality flags
    suspicious_flag = models.BooleanField(default=False)
    confidence_score = models.IntegerField(default=100)  # 0-100%
    
    # Audit state
    locked_for_audit = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'emission_record'
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['data_source']),
        ]
    
    def __str__(self):
        return f"{self.category}: {self.normalized_value} {self.normalized_unit}"


class ValidationIssue(models.Model):
    """
    Validation results for a record.
    
    Why separate model:
    - One record can have multiple issues
    - Analyst needs to see all issues for a record
    - Issues can be resolved over time (audit trail)
    - Enables data quality scoring
    """
    id = models.AutoField(primary_key=True)
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='issues')
    
    issue_type = models.CharField(
        max_length=50,
        choices=[
            ('negative_value', 'Negative Value'),
            ('missing_date', 'Missing Activity Date'),
            ('invalid_unit', 'Invalid/Unknown Unit'),
            ('duplicate_row', 'Potential Duplicate'),
            ('outlier_high', 'Value Unusually High'),
            ('outlier_low', 'Value Unusually Low'),
            ('missing_context', 'Missing Context (plant, employee)'),
            ('invalid_date_format', 'Invalid Date Format'),
            ('zero_value', 'Zero Value'),
            ('other', 'Other'),
        ]
    )
    
    severity = models.CharField(
        max_length=20,
        choices=[
            ('error', 'Error - Blocks Approval'),
            ('warning', 'Warning - Needs Review'),
            ('info', 'Info - FYI'),
        ]
    )
    
    description = models.TextField()
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'validation_issue'
    
    def __str__(self):
        return f"{self.issue_type}: {self.record}"


class AuditLog(models.Model):
    """
    Complete audit trail. MANDATORY for enterprise systems.
    
    Every change to a record must be logged:
    - Who made the change
    - When
    - What changed
    - Old value vs new value
    
    This enables:
    - Compliance audits
    - Data lineage
    - Dispute resolution
    - Regulatory compliance (e.g., for carbon verification)
    """
    id = models.AutoField(primary_key=True)
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    
    action = models.CharField(
        max_length=50,
        choices=[
            ('created', 'Record Created'),
            ('updated', 'Record Updated'),
            ('approved', 'Record Approved'),
            ('locked', 'Record Locked'),
            ('issue_flagged', 'Issue Flagged'),
            ('issue_resolved', 'Issue Resolved'),
        ]
    )
    
    changed_by = models.CharField(max_length=255)  # email/username
    field_name = models.CharField(max_length=100, blank=True)  # Which field changed
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.action} by {self.changed_by} at {self.timestamp}"
