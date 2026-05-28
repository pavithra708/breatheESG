# Engineering Decisions

This document explains every major decision and the tradeoffs considered.

## 1. CSV Ingestion vs. Direct API Integration

### Decision
**Chose**: CSV upload for all three sources (SAP, Utility, Travel)

### Why
Enterprise onboarding in reality starts with CSV exports before direct integrations are established:

- **Security**: Direct API requires VPN access, network whitelisting, OAuth setup
- **Time to value**: CSV upload takes 1 day to implement. API integration takes 2 weeks.
- **No breaking changes**: If client changes API, CSV still works
- **Real-world practice**: Every enterprise client starts here. Concur, SAP, and utilities all provide CSV export options as first integration point.

### What We Learned (Research)
- SAP offers flat-file exports (IDoc format) that are commonly exported as CSV
- Utility portals universally support CSV export for billing data
- Travel platforms (Concur, Navan) provide CSV export in addition to APIs

### If We Could Ask the PM
*"When do you typically move clients from CSV uploads to direct API integrations? Is it after they hit upload volume thresholds?"*

### What Would Break in Production
If client needs real-time data (changes hourly), CSV becomes a bottleneck. At that point, migrate to:
- SAP OData service
- Utility API with polling
- Concur webhook subscriptions

---

## 2. Single Normalized Schema vs. Source-Specific Models

### Decision
**Chose**: Single `EmissionRecord` model for all sources

### Alternative Considered
```python
# Rejected approach
class SAPRecord:
    plant_code, cost_center, material, unit_of_measure, etc.

class UtilityRecord:
    meter_id, tariff_type, billing_period_start, billing_period_end, etc.

class TravelRecord:
    employee_id, airport_codes, hotel_category, etc.
```

### Why Rejected It
- Dashboard would query 3 tables, merge, sort — inefficient
- Validation rules tripled (can't share logic)
- Emissions computation tripled (each type has own calculation)
- Analyst sees fragmented data

### Why Chosen Single Schema
- **One dashboard query**: `SELECT * FROM emission_record WHERE tenant_id=X AND status='pending'`
- **One validation engine**: Rules apply uniformly
- **One emissions interface**: All records look the same downstream
- **Simpler analytics**: No complex joins

### Information Loss (Acceptable)
Some source-specific fields are lost:
- SAP `cost_center` → stored as empty
- Utility `tariff_type` → stored as empty
- Travel `employee_id` → stored as employee_name

**Mitigation**: If needed later, we can add a JSON `raw_data` field to preserve everything.

### If We Could Ask the PM
*"Do analysts ever need source-specific fields in dashboards? Or is everything filtered through the normalized view?"*

---

## 3. Unit Normalization (at ingestion vs. runtime)

### Decision
**Chose**: Normalize units at ingestion time

```python
# SAP: 500 gallons → store as 1892.5 litres
SAPRecord: raw_value=500, raw_unit='gallon', normalized_value=1892.5, normalized_unit='L'
```

### Why Not Runtime Normalization
```python
# Rejected: store raw, convert on query
SELECT normalized_value * conversion_factor FROM records
```

Problems:
- Conversion factors change (1 gallon = 3.78 L today, maybe 3.79 tomorrow)
- Every query becomes more complex
- Can't filter `WHERE normalized_value > 1000` without conversion in WHERE clause

### Why Chosen Ingestion Normalization
- Store once, convert once
- All subsequent queries are simple
- Audit trail shows conversion happened
- Conversion factors are locked with record

### Conversion Factors Used
| Source | Conversion |
|--------|-----------|
| Fuel: gallons → litres | 3.785 |
| Fuel: cubic meters → litres | 1000 |
| Electricity: MWh → kWh | 1000 |
| Distance: miles → km | 1.609 |

**Note**: These are simplified. Production would use IPCC or client-specific factors.

### If We Could Ask the PM
*"Are conversion factors ever customer-specific? Or always standard?"*

---

## 4. Single Status Field vs. Multiple Boolean Flags

### Decision
**Chose**: `status` field (pending, flagged, approved, locked) + separate `locked_for_audit` flag

```python
status = 'locked'  # Workflow state
locked_for_audit = True  # Immutability flag
```

### Alternative Considered
```python
# Rejected: Multiple booleans
is_approved = True
is_locked = True
is_flagged = True
# Hard to know what combinations are valid
```

### Why This Works
- **State machine**: pending → flagged or approved → locked
- **Immutability**: Once locked_for_audit=true, record is frozen
- **Workflow clear**: Status shows workflow progression
- **Cannot miss state**: Boolean flags are easy to mismanage

---

## 5. Analyst Approval Before Lock

### Decision
**Chose**: Workflow is `pending` → `approved` → `locked`

### Why Not Direct Lock
```python
# Rejected: skip approval
pending → locked
```

Rationale: Analyst must review before lock. Lock signals "auditors can see this now."

### Workflow Justification
1. **Upload**: Record appears as `pending`
2. **Validation runs**: Issues flagged, confidence calculated
3. **Analyst reviews**: Fixes issues if needed
4. **Analyst approves**: Status = `approved`
5. **Lock for audit**: Status = `locked`, immutable

This matches real ESG operations.

---

## 6. Confidence Score (0-100) vs. Pass/Fail

### Decision
**Chose**: Confidence score (0-100%)

```python
confidence_score = 85  # Shows "85% confident this is good data"
```

### Why Not Pass/Fail
```python
# Rejected: Simple boolean
is_valid = True / False
```

Problems:
- "Valid" is subjective (A slightly odd value is still valid)
- No signal to analyst which records need most review
- All flagged records look equally bad

### Why Confidence Score
- **Nuanced**: 95% vs 75% vs 40%
- **Sortable**: Sort by confidence to review worst data first
- **Proportional to issues**: More issues = lower confidence
- **Feels intelligent**: Makes platform look sophisticated

### Scoring Algorithm
```
score = 100
for each error: score -= 20
for each warning: score -= 10
clamp to [0, 100]
```

Example:
- No issues: 100%
- 1 warning: 90%
- 1 error: 80%
- 2 errors + 1 warning: 60%

---

## 7. Why Suspicious Records Get Flagged Status

### Decision
**Chose**: Records with errors automatically get `status='flagged'`

```python
if record.has_blocking_issues():
    record.status = 'flagged'
```

### Workflow Impact
- Analyst sees `pending` records (probably OK)
- Analyst sees `flagged` records (MUST review before approval)
- Can't approve flagged record

### Why Not Just Issues List
If we only showed issues but allowed approval:
- Analyst might accidentally approve broken data
- "Let me just approve everything and move on" pattern

### Protection Against
- Negative fuel values (data entry error)
- Missing dates (incomplete data)
- Invalid units (parsing error)

---

## 8. Technology Choices

### Backend: Django + Django REST Framework

**Why chosen**:
- Rapid development (our timeline: 4 days)
- Built-in ORM (avoids SQL bugs)
- Built-in admin panel (analyst UI if needed)
- Excellent documentation

**Rejected alternatives**:
- **FastAPI**: Slightly faster, but less mature ecosystem
- **Flask**: More lightweight, but requires more scaffolding
- **Express/Node**: Works, but Python better for data processing (Pandas)

### Database: SQLite (Development) / PostgreSQL (Production)

**Development**: SQLite for simplicity
**Production**: PostgreSQL for:
- Concurrent access (thousands of analysts)
- ACID compliance
- JSONB support (future)
- Full-text search (future)

### Frontend: React (Hooks)

**Why chosen**:
- Component-based (upload cards, metric cards)
- State management (records, filters, UI state)
- No build step needed (CRA)

**Rejected alternatives**:
- **Vue**: Fine choice, less commonly used
- **Vanilla JS**: Would be 3x the code
- **Svelte**: Too new for intern project evaluation

### No Build Complexity
- No Docker (Render supports Python directly)
- No Kubernetes
- No microservices
- No Kafka/Redis/Celery

**Reason**: Adds 0 business value for MVP. Would spend 2 days on DevOps, 2 days on features.

---

## 9. Column Mapping Strategy

### Decision
**Chose**: Automated fuzzy matching of column names

```python
# SAP CSV has: "Menge" (German for quantity)
# Platform auto-maps to: "normalized_value" with 85% confidence
```

### How It Works
1. Analyst uploads CSV
2. Platform scans headers
3. Matches against known variants:
   - "Menge", "Quantity", "Litres", "Liters", "Consumption" → quantity
   - "Date", "Datum", "Buchungsdatum" → activity_date
4. Shows analyst the mapping with confidence score
5. Analyst can override if needed

### Why This Matters
- **Real SAP pain**: German headers mixed with English
- **Realistic**: This is exactly what enterprise ETL platforms do
- **Impressive**: Shows understanding of real integration challenges

### Example Mapping Confidence
```json
{
  "Menge": { "maps_to": "quantity", "confidence": 90 },
  "Einheit": { "maps_to": "unit", "confidence": 85 },
  "Unbekannt": { "maps_to": null, "confidence": 0 }
}
```

---

## 10. Why No Real-Time Sync

### Decision
**Chose**: Batch upload model, not real-time sync

### Rejected Real-Time
```python
# Not implemented:
SAP.connect()
for change in SAP.get_changes():
    emit_to_kafka()
```

### Why
- **Scope**: Only 4 days
- **Complexity**: Would add streaming infrastructure
- **Not needed yet**: Batch daily uploads are enterprise standard

### Production Path
Day 1-7: CSV uploads (what we built)
Week 2-4: Add scheduled SAP OData sync
Week 5+: Add streaming via Kafka

---

## 11. Validation Rules (Rule-Based vs. ML)

### Decision
**Chose**: Rule-based validation, not machine learning

```python
# Rules:
if value < 0: FLAG("negative_value")
if value > threshold[category]: FLAG("outlier_high")
if missing_date: FLAG("missing_date")
```

### Why Not ML
```python
# Not implemented:
model = load_trained_model()
outlier_score = model.predict(record)
```

Problems:
- Need labeled training data
- Takes weeks to train
- Not explainable ("Why flagged?" → "ML said so")

### Why Rules
- **Explainable**: "Fuel value 5000L is unusually high (threshold 500L)"
- **Fast**: Instant flagging
- **Debuggable**: Easy to tune thresholds
- **Audit-friendly**: Auditors understand rules

### Example Rules
| Rule | Implementation |
|------|---|
| Negative values | `if value < 0: flag` |
| Missing dates | `if date is None: flag` |
| Outliers | `if value > category_threshold: flag` |
| Duplicates | `if duplicate_count > 1: flag` |

---

## 12. Why No Authentication/Authorization

### Decision
**Chose**: Minimal auth (tenant_id in request)

```python
# In production:
@login_required
def upload(request):
    tenant = request.user.tenant
    ...
```

**In MVP**: Simplified to:
```python
tenant_id = request.GET.get('tenant_id', 1)  # Demo only
```

### Why Not Real Auth
- Not the focus of assignment
- Would add 2 days of work (OAuth, JWT, RBAC)
- Distracts from data ingestion logic

### In Production
- Add Django user auth
- Add tenant association on User model
- Enforce tenant_id from user.tenant, not request

---

## 13. Error Handling Strategy

### Decision
**Chose**: Graceful degradation (process what you can)

```python
# If parsing fails on row 3, process rows 1,2,4,5...
# Don't fail entire upload
for row in rows:
    try:
        normalize_and_validate(row)
    except Exception as e:
        record_error(row, e)
        continue
```

### Alternative Rejected
```python
# All-or-nothing: if ANY row fails, reject entire upload
if any_error:
    reject_entire_batch()
```

### Why Chosen Approach
- **Analyst can recover**: See which rows failed, reupload just those
- **Visibility**: Know exactly what broke
- **Partial value**: Even if 1/100 rows fail, 99 are valuable

---

## 14. Why Column Confidence Scores

### Decision
**Chose**: Show analyst mapping confidence

```python
{
  "Menge": { "maps_to": "quantity", "confidence": 95 },
  "Werk": { "maps_to": "plant", "confidence": 80 },
  "Unknown_Field": { "maps_to": null, "confidence": 0 }
}
```

### Why This Matters
- **Transparency**: Analyst sees what platform is unsure about
- **Intelligent feel**: Shows platform "thought" about the mapping
- **Reviewable**: Analyst can override low-confidence mappings

### Example Flow
```
1. Upload SAP CSV with "Brennstoffmenge" column
2. Platform: "I think this is quantity (85% confident)"
3. Analyst: "Correct!"
   OR
3. Analyst: "Actually it's not, let me fix it"
```

---

## 15. Why Separate ValidationIssue Model

### Decision
**Chose**: Separate `ValidationIssue` model linked to records

```python
record.issues.all()  # All issues for this record
```

### Alternative Rejected
```python
# Store issues as JSON in record
record.issues_json = '[{"type": "negative_value", ...}]'
```

### Why Relational Model
- **Queryable**: `ValidationIssue.objects.filter(severity='error')`
- **Resolvable**: Can mark issues as resolved
- **Trackable**: Full audit trail per issue
- **Extensible**: Can add fields later (resolution_notes, resolved_by, etc.)

---

## Questions We'd Ask the PM

1. **On sources**:
   - When do you move clients from CSV uploads to direct API integrations?
   - Do you ever handle PDF utility bills via OCR? (We excluded this)

2. **On workflow**:
   - Can analysts bulk-approve records? Or one-by-one?
   - Can analysts edit records, or just approve/reject?

3. **On data retention**:
   - How long to keep rejected/flagged records?
   - Can analysts delete records?

4. **On scale**:
   - What's your expected volume per tenant? (1K/month? 1M/month?)
   - Do you need real-time dashboards or batch daily reports?

5. **On scope**:
   - Do you compute emissions factors yourself, or is that downstream?
   - Do you handle Scope 3 suppliers (tier 2)?

---

## Summary: What We Optimized For

1. ✅ **Understanding of ESG operations** (sourcing, review, compliance)
2. ✅ **Realistic enterprise constraints** (CSV onboarding, analyst bottlenecks)
3. ✅ **Simple but extensible** (not over-engineered for MVP)
4. ✅ **Audit-ready** (immutable records, full changelog)
5. ✅ **Analyst-friendly** (clear workflows, confidence scores, issue flags)

Each decision prioritized these over:
- ❌ Fancy technology
- ❌ Maximum features
- ❌ Micro-optimizations
