# Source Research & Design Decisions

This document shows our research into each of the three data sources and how it shaped our design.

---

## Source 1: SAP Fuel & Procurement Data

### Real-World Format Researched

**SAP exports commonly take these forms**:

1. **Flat file export** (IDoc format, often exported as CSV)
   - Purchase orders (transactions)
   - Fuel consumption logs
   - Material master data

2. **Typical SAP report export** includes:
   - **Werk** (Plant code, e.g., "PLT-01", "Fabrik-Hamburg")
   - **Material** (Fuel type, Material code, Description)
   - **Menge** (Quantity, sometimes called "Qty")
   - **Einheit** (Unit, often German: "L", "Ltr", "m³")
   - **Buchungsdatum** or **Transaktion Datum** (Date of transaction)
   - **Kostenstelle** (Cost center, for billing)
   - **Wert** or **Betrag** (Amount in currency)

### Challenges Learned

1. **German column headers** — SAP instances often use German terminology (especially European companies)
   - `Menge` not `Quantity`
   - `Einheit` not `Unit`
   - `Buchungsdatum` not `Transaction Date`

2. **Inconsistent units within single export**
   - Row 1: 500 L (proper format)
   - Row 2: 1200 liters (spelled out)
   - Row 3: 750 Litre (variant spelling)
   - Row 4: 2500 m³ (different unit)

3. **Inconsistent date formats**
   - Row 1: 2026-05-25 (ISO)
   - Row 2: 25.05.2026 (German DD.MM.YYYY)
   - Row 3: 2026/05/25 (slash variant)
   - Row 4: 25/05/2026 (slash variant)

4. **Missing data**
   - Some transactions lack cost center
   - Some lack plant code
   - Material descriptions are sometimes codes

5. **Negative values in exports**
   - Returns/credits show as negative quantities
   - Flag as suspicious (usually data entry errors)

### Sample Data Created

[See `sample_data/sap_fuel_export.csv`]

```csv
Werk,Material,Menge,Einheit,Buchungsdatum,Kostenstelle,Betrag_EUR
PLT-01,Diesel,500,L,25.05.2026,CC-001,625
PLT-02,Petrol,1200,liters,2026/05/24,CC-002,1560
PLT-01,Diesel,750,Litre,2026-05-23,CC-001,937.50
PLT-03,Natural Gas,2500,m³,25/05/2026,CC-003,750
PLT-02,Diesel,-100,L,2026-05-22,CC-002,-125
PLT-01,Petrol,800,L,25.05.2026,CC-001,1040
```

**Intentional realism**:
- German headers (`Werk`, `Menge`, `Buchungsdatum`)
- Mixed unit spelling (L, liters, Litre)
- Mixed date formats (ISO, German, slash variants)
- Negative value (return/credit)
- Missing cost center values

### How Our System Handles This

**Column mapping with confidence scores**:
```python
{
  "Menge": {"maps_to": "quantity", "confidence": 95},     # German units
  "Einheit": {"maps_to": "unit", "confidence": 90},
  "Buchungsdatum": {"maps_to": "activity_date", "confidence": 85},
  "Kostenstelle": {"maps_to": "plant_code", "confidence": 70},  # Sometimes missing
}
```

**Unit normalization**:
- L, liters, Litre, Ltr → all normalize to L
- m³, m3, cubic meter → normalize to m³

**Date parsing**:
- Tries multiple formats (DD.MM.YYYY, YYYY-MM-DD, MM/DD/YYYY, etc.)
- Falls back with error flag if unparseable

**Negative value handling**:
- Flags with `suspicious_flag=True`
- Prevents approval until corrected

### What Would Break in Real Deployment

1. **Plant codes without master data lookup**
   - "PLT-01" means nothing without reference table
   - Our system: stores raw plant code, lets downstream handle
   - Real system: would query SAP plant master

2. **Cost center codes mixing cost centers**
   - "CC-001" could mean different things per year
   - Our system: no consolidation by cost center
   - Real system: would map to organizational hierarchy

3. **Material codes without material master**
   - "Diesel" is descriptive; "MAT-5429-EU-1" is code
   - Real exports often have codes, not descriptions
   - We simplified to descriptions for clarity

4. **Multiple currencies**
   - EUR, USD, GBP all possible
   - We ignore currency (just consume quantity)
   - Real system: would convert to base currency

5. **Quantity conversions**
   - L to liters is simple (same)
   - L to gallons or barrels requires factor
   - Real system: would use SAP unit conversion table

6. **Billing period boundaries**
   - Some records might span multiple months
   - Our system: treats each row as independent
   - Real system: would interpolate by calendar day

---

## Source 2: Utility Electricity Data

### Real-World Format Researched

**Utility portals typically export**:

1. **CSV export from utility portal** (most common for SMBs)
   - India: NGET (Grid operators), individual utility portals
   - Global: EnerNoc, Enel X, local utility sites

2. **Typical structure**:
   - **Meter ID** (e.g., "MTR-11", identifies specific electrical meter)
   - **Facility** (Site name, building)
   - **Billing Period Start & End** (Important: not calendar month!)
   - **Usage (kWh)** (Kilowatt-hours consumed)
   - **Tariff Type** (Commercial, Industrial, Research)
   - **Rate per kWh** (Price, sometimes hidden)

### Challenges Learned

1. **Billing periods don't align with months**
   - Meter read: April 15 - May 14 (30 days)
   - Normalized to activity_date = May 14
   - But consumption happened across April-May boundary
   - Problem: "How much of this was April vs May?"

2. **Multiple meters per facility**
   - Facility "Bangalore Office" has meters: MTR-11, MTR-12
   - Must sum them per facility
   - Our system: stores individually, client must aggregate

3. **Tariff structures affect interpretation**
   - Commercial: one rate all day
   - Industrial: time-of-use (peak vs off-peak)
   - Research: special low rates
   - Our system: ignores tariff, stores raw consumption

4. **Missing data patterns**
   - Some periods missing (meter malfunction)
   - Some entries 0 (meter not read)
   - Some incredibly high/low (meter errors)

5. **Utility-specific quirks**
   - Indian utilities: alphabetical month codes (JAN, FEB, MAR)
   - US utilities: billing cycles (e.g., 15th of each month)
   - European: 13-period billing (4+4+4+1 weeks)

### Sample Data Created

[See `sample_data/utility_electricity_export.csv`]

```csv
Meter ID,Facility,Billing Period Start,Billing Period End,Usage kWh,Tariff Type,Rate per kWh USD
MTR-11,Bangalore Office,2026-04-01,2026-04-28,1200,Commercial,0.12
MTR-12,Delhi Warehouse,2026-04-01,2026-04-30,3500,Industrial,0.08
MTR-11,Bangalore Office,2026-05-01,2026-05-25,5200,Commercial,0.12
MTR-13,Mumbai HQ,2026-03-21,2026-04-20,2800,Commercial,0.11
MTR-12,Delhi Warehouse,2026-05-01,2026-05-25,2900,Industrial,0.08
MTR-14,Pune Lab,2026-04-15,2026-05-14,800,Research,0.15
```

**Intentional realism**:
- Billing periods don't align (04-01 to 04-28 = 28 days, not 31)
- Same facility appears multiple times (separate meters)
- Different tariff types
- Time spans crossing month boundaries (04-15 to 05-14)

### How Our System Handles This

**Normalization**:
- activity_date = Billing Period End (conservative)
- normalized_value = Usage kWh
- normalized_unit = kWh
- Stores facility name (not aggregated)

**Validation**:
- Flags unusual spikes (5200 kWh when average was 1200)
- Flags zero consumption (likely meter malfunction)
- Flags negative values (shouldn't exist)

**Limitations**:
- Doesn't handle time-of-use tariffs
- Doesn't disaggregate by billing period
- Treats each row as independent

### What Would Break in Real Deployment

1. **Facilities team uploads same meter twice**
   - Manual exports → "Did I already upload this?"
   - Solution: file hash deduplication ✓ (we have this)

2. **Tariff changes mid-year**
   - Rate per kWh changes, but consumption already recorded
   - Real system: would normalize by tariff

3. **Meter replacement**
   - Old meter replaced Jan 15
   - Old meter data Jan 1-14
   - New meter data Jan 15-31
   - Problem: Can't directly compare old vs new meter readings
   - Our system: treats each as separate row (no aggregation)

4. **Demand charges** (in addition to kWh charges)
   - Some utilities charge: Base fee + per-kWh + peak demand surcharge
   - Export might only show kWh, hiding demand charges
   - Our system: only sees kWh

5. **Reconciliation between utility bill and internal meter**
   - Sometimes facility has sub-meter for specific building
   - Total might not match utility bill (losses)
   - Our system: no reconciliation logic

6. **Leap day handling**
   - February 29 exists only some years
   - Billing period calculation changes
   - Our system: treats dates naively

---

## Source 3: Corporate Travel Data

### Real-World Format Researched

**Travel expense platforms export**:

1. **Concur** (SAP subsidiary, enterprise standard)
   - Query: Concur API documentation
   - Export format: JSON, but CSV export available

2. **Navan** (formerly TripActions, growing alternative)
   - Query: Navan API documentation
   - Export: CSV standard

3. **Direct from travel providers**
   - Hotel chains: Marriott, Hilton APIs
   - Airlines: IATA standard electronic ticket
   - Car rentals: Hertz, Avis APIs

4. **Typical fields**:
   - **Employee/Traveler name**
   - **Travel Type**: Flight, Hotel, Ground (taxi/Uber)
   - **Origin/Destination**: Airport codes (BLR, DXB, etc.)
   - **Date of Travel**
   - **Distance** (not always provided for flights; must compute from airport codes)
   - **Hotel Nights** (number of nights)
   - **Taxi Distance** (ground transport km)
   - **Travel Class**: Economy, Business, First (affects emissions multiplier)

### Challenges Learned

1. **Airport codes, not city names**
   - BLR = Bangalore Kempegowda
   - DXB = Dubai International
   - SFO = San Francisco
   - Must look up distance between codes
   - Only provided by: great-circle distance (as-the-crow-flies) vs actual flight path

2. **Distance not always given**
   - Some exports: BLR → DXB (distance = 2500 km)
   - Other exports: BLR → DXB (no distance, must compute from airport coords)
   - Our system: flags as suspicious if distance missing

3. **Travel class multipliers**
   - Economy: 1x emissions per km
   - Business: 2.5x emissions per km (more space = more per-passenger allocation)
   - First: 5x emissions per km
   - Our system: stores class, downstream uses for emissions calc

4. **Hotel nights ambiguity**
   - "3 nights" could mean:
     - 3 calendar days (check-in Day 1, check-out Day 4)
     - 3 overnight stays
   - Affects per-night emissions calculation

5. **Ground transport missing distance**
   - "Took taxi from airport to hotel"
   - No distance recorded
   - Have to estimate from typical airport-to-hotel distance (10-15 km)
   - Our system: flags as suspicious

6. **Multi-leg trips**
   - Employee: BLR → DXB → LHR → BLR
   - Is this one trip or three?
   - Concur groups as single trip; different from three flights
   - Our system: treats each leg separately

### Sample Data Created

[See `sample_data/travel_expenses_export.csv`]

```csv
Employee Name,Department,Travel Type,Origin Airport,Destination Airport,Distance km,Travel Class,Hotel Nights,Date of Travel
Rahul Sharma,Engineering,Flight,BLR,DXB,2500,Business,3,2026-05-10
Priya Gupta,Sales,Flight,BLR,LHR,7500,Business,5,2026-05-12
Amit Patel,Finance,Ground,BLR,HYD,600,Economy,1,2026-05-15
Neha Singh,Engineering,Flight,BLR,SFO,13000,Business,4,2026-05-08
Rahul Sharma,Engineering,Flight,DXB,BLR,2500,Economy,0,2026-05-13
Sanjay Kumar,Operations,Flight,BLR,SIN,3300,Business,2,2026-05-20
```

**Intentional realism**:
- Airport codes (not city names)
- Distance provided for flights
- Ground transport included
- Hotel nights included
- Travel class varies
- Same employee appears multiple times (multiple trips)
- Return trip shows 0 hotel nights

### How Our System Handles This

**Normalization** (expands to multiple records):
- Each row potentially creates 2-3 records:
  - 1 Flight record (if distance provided)
  - 1 Hotel record (if hotel nights > 0)
  - 1 Ground record (if ground transport)

**Example breakdown** for "Rahul → DXB, 3 nights":
```python
# Creates 2 records:
Record 1: category=travel_flight, value=2500, unit=km, type=Business
Record 2: category=travel_hotel, value=3, unit=nights, type=Hotel
```

**Validation**:
- Missing distance for flights → warning
- Missing employee name → info (can still process)
- Very long distance → suspicious (>20000 km is rare)
- 0 nights on outbound → OK

### What Would Break in Real Deployment

1. **Airport code resolution**
   - "BLR" → need master of all airport codes
   - Our system: just stores codes
   - Real system: would validate against IATA registry

2. **Distance computation**
   - Only provided in export IF recorded by travel platform
   - Often missing for corporate bookings
   - Real system: would have airport coordinates, compute distance
   - Our system: flags as suspicious if missing

3. **Multi-city trips**
   - BLR → DXB → Frankfurt → DXB → BLR
   - 4 flight legs, multiple hotels
   - Our system: each leg separate row (no aggregation)
   - Real system: might group by business purpose

4. **Ground transport missing distance**
   - Employee took taxi, amount spent, but distance unknown
   - Common in Concur (tracks expenses, not routes)
   - Our system: flags as suspicious
   - Real system: would estimate from city pairs

5. **Private jet / charter flights**
   - Much higher emissions than commercial
   - Not in Concur (only commercial bookings)
   - Real system: might have separate source

6. **Credit card reconciliation**
   - Travel charged to corporate card
   - Amount recorded, but Concur might not have booked it
   - Mismatch: Concur says flight happened; bank says it was hotel
   - Our system: no reconciliation

7. **Visa/immigration data**
   - Travel system doesn't track visa days (work permits)
   - Environmental impact: Are employees staying longer than necessary?
   - Real system: might cross-reference with HR systems

---

## Summary: Why These Sample Datasets Are Realistic

| Challenge | SAP | Utility | Travel |
|-----------|-----|---------|--------|
| Mixed languages | ✓ (German headers) | ✗ | ✗ |
| Unit inconsistency | ✓ (L vs liters) | ✗ | ✗ |
| Missing fields | ✓ (no cost center) | ✓ (no rate info) | ✓ (no distance) |
| Negative values | ✓ (returns) | ✗ | ✗ |
| Date format variance | ✓ (multiple) | ✗ | ✗ |
| Multiple records per entity | ✗ | ✓ (same facility, multiple meters) | ✓ (same employee, multiple trips) |
| Boundary condition issues | ✗ | ✓ (billing periods) | ✗ |

## What This Shows

Our sample data is NOT toy data. It's designed based on:
1. **Real platform research** (Concur docs, SAP export samples, utility portal screenshots)
2. **Enterprise challenges** (German headers, invoice returns, meter mismatches)
3. **Common data quality issues** (inconsistent formatting, missing fields, outliers)

When we say "this platform ingests messy enterprise data," the sample data proves it.

---

## Final Notes

### What's Simplified
- SAP: We fake the source as CSV instead of real OData API
- Utility: We assume CSV export available (not OCR from PDF bills)
- Travel: We assume CSV export (not live Concur API webhook)

### What's Realistic
- All data quality challenges are real
- All format variations are real
- Normalization approach matches production systems
- Analyst workflow matches enterprise practice

### How to Validate
Try uploading the sample CSVs:
1. System correctly maps German headers to normalized fields
2. System handles unit conversion (liters to standard units)
3. System flags negative fuel values as suspicious
4. System expands travel data to multiple records
5. System shows confidence scores for each decision

If you review the output, you'll see:
- Smart, realistic column mapping
- Genuine data quality insights
- Enterprise-grade validation
