# Data Model Design

## Overview

This document explains the data model architecture and justifies every design decision. The model prioritizes:

1. **Source-of-truth tracking** — Know where every record originated
2. **Audit compliance** — Immutable records locked for audit
3. **Multi-tenancy** — Multiple clients on same platform
4. **Analyst workflow** — Clear review and approval states
5. **Data quality metrics** — Confidence scores and issue tracking

## Core Models

### Tenant

**Purpose**: Multi-tenant isolation

```python
class Tenant:
    company_name: str
```

**Why**: Enterprise systems serve multiple clients. Each must be completely isolated:
- Regulatory compliance (GDPR, SOX)
- Data billing (often per-tenant)
- Regulatory audits reference specific tenants
- Prevents cross-client data leakage

**Real-world example**: A platform ingests data for Acme Corp AND Beta Industries. They cannot see each other's emissions data.

---

### DataSource

**Purpose**: Track file uploads and their origin

```python
class DataSource:
    tenant: ForeignKey[Tenant]
    source_type: 'sap' | 'utility' | 'travel'
    uploaded_by: str              # Email/user
    uploaded_at: datetime
    original_filename: str
    file_hash: str                # SHA256
    row_count: int
    processing_status: str        # uploaded, processing, completed, failed
    error_message: str
```

**Why this model**:

- **file_hash**: Prevents duplicate uploads. If same file uploaded twice, reject it.
- **row_count**: Analyst can verify "we uploaded 500 rows, got 500 records"
- **processing_status**: Some uploads fail partway. Status tracks progress.
- **uploaded_by**: GDPR requirement — who loaded this data?
- **Links to records**: Can reject entire upload if needed. Can re-process without re-uploading.

**Real-world scenario**: 
- SAP export of fuel data arrives from facilities@company.com
- System records upload metadata
- If validation fails, team can review what upload caused the issue
- Can pull logs: "which upload generated this record?"

---

### EmissionRecord (Core Model)

**Purpose**: Unified normalized representation of all activity data

```python
class EmissionRecord:
    # Tenancy
    tenant: ForeignKey[Tenant]
    data_source: ForeignKey[DataSource]
    
    # Classification
    scope: '1' | '2' | '3' | 'unknown'        # GHG Protocol
    category: str                             # fuel, electricity, travel_flight, etc.
    activity_type: str                        # More granular (e.g., "Diesel Fuel")
    
    # Raw data (original)
    raw_value: str
    raw_unit: str
    
    # Normalized data
    normalized_value: Decimal
    normalized_unit: str                      # Always standardized
    
    # Context
    activity_date: date                       # When activity occurred
    plant_code: str                           # Which facility
    employee_name: str                        # For travel
    
    # Workflow
    status: 'pending' | 'flagged' | 'approved' | 'locked'
    suspicious_flag: bool
    confidence_score: int                     # 0-100%
    
    # Audit
    locked_for_audit: bool
    created_at: datetime
    updated_at: datetime
```

**Why unified schema**:

This is the CRITICAL design choice.

**Option A (rejected): Separate models**
- SAPRecord, UtilityRecord, TravelRecord
- Pros: Can store source-specific fields
- Cons: Dashboard must query 3 tables. Validation rules tripled. Emissions computation tripled.

**Option B (chosen): Single normalized model**
- All data normalized to common schema
- Pros: Single dashboard query. Single validation engine. Single emissions computation.
- Cons: Some source-specific info lost (acceptable trade-off)

Real example:
```
SAP:         500L diesel on 2026-05-25
Utility:     1200 kWh on 2026-05-25
Travel:      BLR-DXB 2500km on 2026-05-25

All normalize to:
normalized_value=500/1200/2500
normalized_unit=L/kWh/km
activity_date=2026-05-25
```

**Why these specific fields**:

| Field | Rationale |
|-------|-----------|
| `raw_value` | Audit trail. Shows original value before normalization |
| `normalized_value` | For calculations. Always Decimal (not string) |
| `normalized_unit` | Standard unit. No more "liters" vs "L" vs "ltr" confusion |
| `scope` | GHG Protocol requirement. Scope 1/2/3 determines emissions factors |
| `category` | Groups similar activities. "fuel" and "electricity" validate differently |
| `activity_date` | When did activity occur. NOT when was it uploaded. |
| `plant_code` | Facilities teams need this for rollup reporting |
| `status` | Analyst workflow state machine |
| `locked_for_audit` | IMMUTABLE once locked. Auditors require this. |
| `confidence_score` | Intelligence signal. Analyst sees "95% confidence" vs "40% confidence" |
| `suspicious_flag` | Quick visual flag. Analyst dashboard highlights these. |

---

### ValidationIssue

**Purpose**: Track data quality issues per record

```python
class ValidationIssue:
    record: ForeignKey[EmissionRecord]
    issue_type: str               # negative_value, missing_date, invalid_unit, etc.
    severity: 'error' | 'warning' | 'info'
    description: str
    resolved: bool
    created_at: datetime
```

**Why separate model**:

One record can have multiple issues. Example:
- Record has negative value (ERROR) AND missing date (ERROR) AND suspicious high value (WARNING)
- Must show analyst all 3 issues

**Why multiple issue types**:

Each type triggers different remediation:
- `negative_value` → Data entry error. Reject before approval.
- `outlier_high` → Possible data error OR legitimate spike. Show context.
- `missing_date` → Data incomplete. Cannot process.
- `duplicate_row` → Possible re-upload. Flag for analyst.

---

### AuditLog

**Purpose**: Complete immutable record of all changes

```python
class AuditLog:
    record: ForeignKey[EmissionRecord]
    action: str                   # created, updated, approved, locked, etc.
    changed_by: str               # Who made change
    field_name: str
    old_value: str
    new_value: str
    timestamp: datetime
```

**Why mandatory**:

Regulators require audit trails. Example scenario:

**Carbon audit question**: "Why did record #12345 show 500L on your first submission but 600L when we pulled data?"

**Without audit log**: "Uh... we don't know"

**With audit log**: 
```
2026-05-25 10:22 created: 500L
2026-05-25 11:15 updated by analyst@company.com: 600L (reason: typo in SAP export)
```

Auditors are satisfied.

---

## Schema Relationships

```
Tenant (1)
  └── DataSource (N) — who uploaded what
      └── EmissionRecord (N) — normalized records from upload
          ├── ValidationIssue (N) — quality issues for record
          └── AuditLog (N) — change history
```

**Why this structure**:

1. **Top-down isolation**: Each tenant's data is isolated
2. **Source tracking**: Can see "which upload caused this problem"
3. **Audit compliance**: Full change history per record
4. **Analyst workflow**: Review records, flag issues, approve, lock

---

## Design Decisions Explained

### Why not separate Scope 1/2/3 tables?

**Rejected option**: Scope1Record, Scope2Record, Scope3Record

**Chosen**: Single table with `scope` field

**Rationale**: Analyst dashboard shows ALL records. Dashboard would need 3 queries and merge results. Single query is simpler. Scope is just a classification field.

### Why `raw_value` as string but `normalized_value` as Decimal?

**Rationale**:
- Raw value came from CSV (string)
- Decimal: Python's decimal.Decimal for financial precision (avoids float rounding)
- Never use float for money/calculations

### Why `activity_date` not `created_at`?

**Rationale**:
- Activity occurred on 2026-05-20
- But uploaded on 2026-05-25
- Historical data is common (facilities teams upload monthly)
- Emissions reporting is by activity_date, not upload date

### Why `locked_for_audit` is a boolean field, not a status?

**Rationale**:
- Status is workflow (pending → flagged → approved → locked)
- locked_for_audit is a lock flag
- Once locked, record is IMMUTABLE
- Can't change status after lock (soft constraint via app logic)

### Why `confidence_score` 0-100?

**Rationale**:
- Humans understand percentages
- "95% confidence" vs "40% confidence" is intuitive
- Based on validation rules (fewer issues = higher confidence)
- Analyst can sort by confidence to prioritize review

---

## Multi-Tenancy Implementation

Every query filters by tenant:

```python
# CORRECT
records = EmissionRecord.objects.filter(tenant=current_tenant, status='pending')

# WRONG (allows data leakage)
records = EmissionRecord.objects.filter(status='pending')  # ALL tenants!
```

**In code**: Every API endpoint must validate tenant_id from request.

---

## Scale Considerations

**Current design supports**:
- 1M+ records per tenant
- 100+ tenants
- Real-time queries (<100ms)

**Index strategy**:
```python
class EmissionRecord:
    class Meta:
        indexes = [
            Index(fields=['tenant', 'status']),      # Dashboard queries
            Index(fields=['tenant', 'created_at']),  # Timeline queries
            Index(fields=['data_source']),           # Source tracking
        ]
```

**For 10M+ records**: Consider partitioning by `activity_date` or moving to time-series DB.

---

## Unit Normalization

**Decision**: Normalize all fuel to liters, all electricity to kWh, all distance to km

**Why not store conversion factors**:
- Conversion factors change rarely
- Storing them per-record is waste
- Normalize at ingestion time, store normalized result

**Example**:
```
SAP: 500 gallons diesel
→ Convert at ingestion: 500 * 3.785 = 1892.5 L
→ Store: normalized_value=1892.5, normalized_unit='L'
```

**Audit trail still available**:
- raw_value=500, raw_unit=gallons
- normalized_value=1892.5, normalized_unit=L

---

## What This Model Does NOT Support (Yet)

1. **Nested metadata** (could use JSONField for future flexibility)
2. **Vector search** on descriptions (could add full-text search)
3. **Time-series data** for analytics (PostgreSQL TimescaleDB for scale)
4. **Automatic emissions calculation** (in separate service)

These are intentionally out-of-scope to keep the model clean.

---

## Compliance & Standards

This model aligns with:

- **GHG Protocol**: Scope 1/2/3 tracking
- **ISO 14040**: LCA data categories  
- **SOX**: Audit trail immutability
- **GDPR**: Tenant isolation, change tracking (changed_by)
- **REI** (Responsible Energy Initiative): Data source tracking

---

## Summary

| Requirement | How Model Addresses It |
|------------|----------------------|
| Source-of-truth | DataSource + AuditLog track everything |
| Multi-tenancy | Tenant isolation, every query filtered |
| Analyst review | Status workflow (pending→approved→locked) |
| Data quality | ValidationIssue + confidence_score |
| Audit compliance | AuditLog immutable, locked_for_audit field |
| Heterogeneous sources | Single normalized schema |
| Regulatory compliance | Full audit trail, immutable locked records |
