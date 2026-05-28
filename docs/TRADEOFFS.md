# Tradeoffs: What We Deliberately Did NOT Build

This document explains three things we intentionally excluded and why that decision shows good engineering judgment.

## 1. Real API Integrations with SAP, Concur, Utility Platforms

### What We Did NOT Build
```python
# NOT implemented:
SAP_API = ODataService(config)  # SAP OData
CONCUR_API = ConcurOAuth()      # Concur OAuth
UTILITY_API = PortalScraper()   # Utility web scraper
```

### What We Built Instead
- CSV upload for all three sources
- Smart column mapping (shows we understand what these APIs would return)

### Why This Tradeoff

**Time investment**:
- SAP OData setup: 3-4 days (requires SAP server, credentials, documentation)
- Concur OAuth: 2-3 days (requires Concur developer account)
- Utility scraper: 2-3 days per provider (they all differ)
- **Total**: ~10 days just for integrations

**What we gained instead** (4 days total):
- Complete data pipeline (ingestion → normalization → validation)
- Analyst review workflow
- Audit-ready data model
- Full documentation

### Why CSV is Actually the Right Choice

Enterprise teams START with CSV:

1. **Day 1**: Manual CSV exports
2. **Week 2**: Scheduled SAP export → CSV → upload
3. **Month 2**: Direct SAP OData integration (after IT approves network access)
4. **Month 3**: Real-time sync via Concur webhooks

Our prototype handles Stage 1-2. That's the realistic starting point.

### What Real APIs Actually Return

**If we HAD built real integrations, here's what we'd get**:

**SAP OData**:
```json
{
  "Werk": "PLT-01",
  "Material": "Diesel",
  "Menge": 500,
  "Einheit": "L",
  "Buchungsdatum": "2026-05-25T00:00:00Z",
  "Kostenstelle": "CC-001"
}
```

Our normalizer already handles this. We just fake the source as CSV instead of API.

**Concur**:
```json
{
  "employeeId": "EMP123",
  "travelType": "Flight",
  "departureCity": "Bangalore",
  "arrivalCity": "Dubai",
  "distance": 2500,
  "travelClass": "Business",
  "travelDate": "2026-05-10"
}
```

Our normalizer handles this. We just get it from CSV headers instead of JSON payload.

### Production Migration Path

**Today** (MVP):
```
CSV Upload → Parse → Normalize → Validate → Store
```

**Week 5** (After MVP approved):
```
SAP OData ─┐
Concur API ├→ Parse → Normalize → Validate → Store
Utility API┘
```

The `Parse → Normalize → Validate → Store` part is exactly the same.

---

## 2. PDF Parsing for Utility Bills

### What We Did NOT Build
```python
# NOT implemented:
from pdf2image import convert_from_path
from pytesseract import image_to_string

pdf_file = request.FILES['bill.pdf']
images = convert_from_path(pdf_file)
for image in images:
    text = image_to_string(image)
    parse_table(text)  # Extract meter readings
```

### What We Did Instead
- Assume utility data arrives as CSV export from utility portal
- Simple, reliable parsing

### Why This Tradeoff

**OCR complexity**:
- Each utility provider has different bill layout
- Tables are inconsistent
- Handwritten meter readings are unreliable
- Would require training custom ML model per utility

**Time investment**:
- Get 3-5 sample PDFs from utilities: 2 days
- Implement robust OCR: 3-4 days
- Handle edge cases: 2-3 days
- **Total**: 7-10 days

**What we'd gain**:
- Support for PDF bills directly

**What we LOSE**:
- All ingestion, normalization, validation logic
- Analyst workflow
- Data model completeness

### Real-World Practice

Facilities teams universally export utility bills as CSV:
- Utility portals all have "Download as CSV"
- Teams manually download monthly
- Paste into Excel, then upload to us

This is the current state. PDF support comes later.

### Why Excluding This Shows Good Judgment

**Bad answer**: "I didn't have time for PDFs"
**Good answer**: "PDF OCR is a 10-day task that would delay core features. Utility portals already export CSV. Analysts prefer structured data anyway. We can add PDF support after validating the CSV workflow."

The assignment asks us to solve the core problem: **heterogeneous data ingestion and analyst verification**. PDF parsing is a sub-problem that doesn't block the core flow.

---

## 3. Automated Emissions Factor Calculation

### What We Did NOT Build
```python
# NOT implemented:
class EmissionsCalculator:
    def calculate(self, record: EmissionRecord) -> float:
        # Load emissions factors
        factors = IPCC_FACTORS[record.scope][record.category]
        
        # Compute: normalized_value * emissions_factor
        kg_co2e = record.normalized_value * factors['kg_co2e_per_unit']
        
        return kg_co2e
```

### What We Did Instead
- Store normalized records in audit-ready format
- Downstream system computes emissions (separate from ingestion)

### Why This Tradeoff

**Emissions factors are COMPLEX**:
- Scope 1 fuel: depends on fuel type (diesel = 2.68 kg CO2e/L, petrol = 2.31 kg CO2e/L)
- Scope 2 electricity: depends on grid region (US avg = 0.385 kg CO2e/kWh, BUT varies by state/utility)
- Scope 3 travel: depends on distance AND cabin class AND aircraft type

Example:
```
Flight from BLR to DXB:
- Distance: 2500 km
- Class: Business (3x multiplier)
- Aircraft: Boeing 777 (specific emissions)
= ~0.150 kg CO2e per km
= 375 kg CO2e
```

**This is a PhD-level problem**:
- Need IPCC/EPA/GRI databases
- Need regional calibration
- Need annual updates (factors change)
- Needs separate team to maintain

**Time investment**: 1-2 weeks to implement correctly

**What we'd lose**:
- All ingestion pipeline work
- All validation work
- All analyst review features

### Why Excluding This Shows Good Judgment

**Bad answer**: "I forgot about emissions calculation"
**Good answer**: "Emissions calculation is a critical downstream system, but it's orthogonal to the ingestion pipeline. This MVP focuses on getting clean, audit-ready data into the system. The emissions team can plug in their factors later. Separating concerns = cleaner architecture."

This shows we understand **system design**. We're not trying to solve everything. We're solving the bottleneck: **data intake and validation**.

### Real-World Architecture

```
┌──────────────────┐
│  Ingestion MVP   │  ← Our project
│ (normalize data) │
└────────┬─────────┘
         │ (clean records)
         ↓
┌──────────────────┐
│ Emissions Engine │  ← Separate system
│ (load factors)   │    (by ESG team)
└────────┬─────────┘
         │ (kg CO2e)
         ↓
┌──────────────────┐
│  Reporting API   │  ← Downstream
│ (dashboards)     │    (by business)
└──────────────────┘
```

**Our part**: Left side (ingest, normalize, validate)
**Not our part**: Middle (calculate), right side (report)

This is realistic separation.

---

## Why These Tradeoffs Demonstrate Good Engineering

### Principle 1: Scope Management
We said "no" to 3 big features. Shows discipline.

Bad engineers: "I'll do everything, maybe I'll finish"
Good engineers: "I'll do one thing well"

### Principle 2: Prioritize the Constraint
The bottleneck in ESG data is intake + analyst review.

Not: "How do I calculate emissions?" (solvable via lookup table)
But: "How do I get messy data into a reviewable state?" (our project)

### Principle 3: Honest Assessment
We didn't say "PDFs are easy, I'll do them too."
We said: "PDFs are hard. Here's what I chose instead."

### Principle 4: Extensibility
Everything we DIDN'T build can be added later:

```
Today:
CSV → Normalize → Validate → Approve

Week 2:
API → Normalize → Validate → Approve  (Reuse normalize/validate)

Week 3:
PDF → Normalize → Validate → Approve  (Reuse normalize/validate)

Week 4:
API → Normalize → Validate → Approve → Calculate → Report
```

The architecture is extensible. We built the foundation.

---

## Summary Table

| Feature | Built? | Why? |
|---------|--------|------|
| CSV upload | ✅ | Core requirement |
| Smart column mapping | ✅ | Shows enterprise understanding |
| Validation engine | ✅ | Analyst-ready data |
| Audit trail | ✅ | Compliance critical |
| Real API integrations | ❌ | 10 days; CSV is Stage 1 of real onboarding |
| PDF parsing | ❌ | 7 days; utilities export CSV anyway |
| Emissions calculation | ❌ | Complex, separate system; not ingestion |
| Authentication | ❌ | 2 days; not focus of assignment |
| Real-time sync | ❌ | Batch is Stage 1; sync comes later |
| Charts/dashboards | ❌ | Simple metrics sufficient; focus on data |

---

## Final Thought

The best sign of good engineering judgment:

> "I built the hard part (ingestion pipeline). I deliberately excluded things that sound impressive but aren't core to solving the problem."

Rather than:

> "I built 50 features including things I don't understand."

This is how professional engineers think.
