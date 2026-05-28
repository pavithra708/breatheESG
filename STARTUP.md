# Breathe ESG — Quick Start Guide

## 1. Setup & Installation (5 minutes)

### macOS / Linux

```bash
# Clone/navigate to project
cd BreatheESG

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py shell

# In Python shell:
from models import Tenant
Tenant.objects.create(company_name="Demo Company")
exit()

# Start backend (Terminal 1)
python manage.py runserver

# Frontend setup (Terminal 2)
cd ../frontend
npm install
npm start
```

### Windows (PowerShell)

```powershell
cd BreatheESG

# Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py shell

# In Python shell:
from models import Tenant
Tenant.objects.create(company_name="Demo Company")
exit()

# Terminal 1
python manage.py runserver

# Terminal 2
cd ..\frontend
npm install
npm start
```

## 2. Access the App

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000/api
- **Django Admin**: http://localhost:8000/admin (optional)

## 3. Test the System

### Step 1: Upload Data
1. Go to http://localhost:3000
2. Click "Upload Data"
3. Choose SAP, Utility, or Travel
4. Upload a CSV from `sample_data/`:
   - `sap_fuel_export.csv`
   - `utility_electricity_export.csv`
   - `travel_expenses_export.csv`

### Step 2: Watch the Pipeline
1. Backend processes upload
2. Shows intelligent column mapping with confidence scores
3. Normalizes data to standard schema
4. Validates for issues (flags problematic records)
5. Creates EmissionRecords in database

### Step 3: Review Dashboard
1. See metrics: Total records, pending, flagged, approved
2. See recent uploads with status
3. See data quality scores

### Step 4: Review Records
1. Click "Review (X)" to see pending records
2. See validation issues for flagged records
3. Click "Approve" for good records
4. Click "Lock" to finalize (immutable for audit)

### Step 5: Check Workflow
1. Try uploading SAP with negative fuel values
2. System flags as suspicious
3. Go to review and see error message
4. Can't approve flagged records with errors

## 4. Explore the Code

### Understanding the Pipeline

1. **Upload**: `backend/views.py` → `UploadViewSet.upload_sap()`
2. **Parse**: `backend/ingestion.py` → `IngestionPipeline.parse_csv()`
3. **Normalize**: `backend/normalization.py` → `SAPNormalizer.normalize_row()`
4. **Validate**: `backend/validation.py` → `ValidationEngine.validate()`
5. **Store**: `backend/views.py` → Creates EmissionRecord + ValidationIssue

### Understanding the Data Model

- Open `backend/models.py`
- Key models:
  - `Tenant` — Company isolation
  - `DataSource` — Upload tracking
  - `EmissionRecord` — Normalized data
  - `ValidationIssue` — Quality issues
  - `AuditLog` — Change history

### Understanding the Frontend

- `frontend/App.js` — Main component
- Three views: Dashboard, Upload, Review
- API calls via `fetch()` to backend

## 5. Try These Scenarios

### Scenario 1: German Headers
Upload `sap_fuel_export.csv`
- See system map "Menge" → "quantity" (95% confidence)
- See "Buchungsdatum" → "activity_date"
- See unit conversion: "liters" → "L"

### Scenario 2: Data Quality Issues
Same SAP file has:
- Row 5: Negative value (-100 L) → Status: FLAGGED
- You CAN'T approve flagged records with errors
- Must fix the issue first

### Scenario 3: Travel Data Expansion
Upload `travel_expenses_export.csv`
- 6 input rows expand to 9-10 output records:
  - Flight BLR→DXB (1 record)
  - Hotel 3 nights (1 record)
  - Flight DXB→BLR (1 record)
  - etc.
- Each gets separate normalized record

### Scenario 4: Duplicate Detection
- Upload same CSV twice
- System blocks: "File hash matches previous upload"
- Shows: "Prevention of duplicate data imports"

## 6. Understanding Key Features

### Column Mapping with Confidence

When you upload SAP with "Menge" header:
```python
{
  "Menge": {
    "maps_to": "quantity",
    "confidence": 95  # High because exact variant match
  },
  "Werk": {
    "maps_to": "plant_code",
    "confidence": 85  # Medium because keyword match
  },
  "Unknown": {
    "maps_to": null,
    "confidence": 0   # Can't map this
  }
}
```

Analyst sees this and can override if needed.

### Unit Normalization

All fuel conversions:
- 500 L → 500 L (no change)
- 1200 liters → 1200 L (normalize spelling)
- 750 Litre → 750 L (normalize spelling)
- 400 gallons → 1514 L (convert US gallon)

### Validation Rules

Every record checked against:
- ✓ No negative values (emissions can't be negative)
- ✓ Has activity date (when did it happen)
- ✓ Value not unusually high (outlier detection)
- ✓ Value not unusually low
- ✓ Unit recognized (not "unknown")
- ✓ Not a duplicate of another record

Severity: `error` (blocks approval) vs `warning` (visible, but can approve)

### Confidence Scoring

Score = 100 - (20 per error) - (10 per warning)
- No issues: 100%
- 1 warning: 90%
- 2 warnings: 80%
- 1 error: 80%
- 2 errors: 60%

Analyst sorts by confidence to review worst data first.

### Immutable Locks

Once analyst clicks "Lock":
- Record status = "locked"
- `locked_for_audit` = true
- CANNOT be edited
- Full audit trail preserved

This is what auditors expect.

## 7. Key Architectural Patterns

### Pattern 1: Multi-tenancy
Every query: `EmissionRecord.objects.filter(tenant=X, ...)`
Prevents data leakage between companies.

### Pattern 2: Audit Trail
Every action logged:
```
created: 2026-05-25 10:22 by upload_service
updated: 2026-05-25 11:15 by analyst (normalized_value: 500 → 600)
approved: 2026-05-25 11:20 by analyst
locked: 2026-05-25 11:25 by system
```

### Pattern 3: Source Tracking
Know which upload produced which record:
```
Record #12345 comes from DataSource #5 (sap_fuel_export.csv, uploaded 2026-05-25)
```

### Pattern 4: Normalized Schema
All data (SAP, Utility, Travel) in single EmissionRecord model:
- scope: Scope 1/2/3
- category: fuel, electricity, travel_flight, etc.
- normalized_value: Always Decimal
- normalized_unit: Always standard (L, kWh, km)

This enables single validation engine + single analyst dashboard.

## 8. Testing the API Directly

### Upload a File
```bash
curl -X POST http://localhost:8000/api/upload/upload_sap/ \
  -F "file=@sample_data/sap_fuel_export.csv" \
  -F "tenant_id=1" \
  -F "uploaded_by=analyst@company.com"
```

### List Records
```bash
curl http://localhost:8000/api/records/?tenant_id=1
```

### Get Dashboard Metrics
```bash
curl http://localhost:8000/api/dashboard/metrics/?tenant_id=1
```

### Approve a Record
```bash
curl -X PATCH http://localhost:8000/api/records/1/approve/ \
  -H "Content-Type: application/json" \
  -d '{"changed_by": "analyst@company.com"}'
```

## 9. Production Deployment

### Render (Recommended)

1. **Backend**:
   ```
   New → Web Service
   Connect GitHub repo
   Environment: Python
   Build command: pip install -r backend/requirements.txt && python backend/manage.py migrate
   Start command: gunicorn backend.wsgi:application
   ```

2. **Database**:
   ```
   New → PostgreSQL
   Note the DATABASE_URL
   ```

3. **Frontend**:
   ```
   New → Web Service
   Connect GitHub repo
   Environment: Node
   Build command: cd frontend && npm install && npm run build
   Start command: npm install -g serve && serve -s frontend/build
   Set REACT_APP_API_URL environment variable
   ```

4. **Environment Variables**:
   Add to both backend and frontend:
   - DATABASE_URL (backend only)
   - SECRET_KEY (backend only)
   - REACT_APP_API_URL=your-backend-url.com (frontend only)

## 10. Troubleshooting

### "ModuleNotFoundError: No module named 'django'"
```bash
source venv/bin/activate  # Activate virtualenv
pip install -r requirements.txt
```

### "npm: command not found"
- Install Node.js from https://nodejs.org/

### "Port 8000 already in use"
```bash
# macOS/Linux: Kill process on port 8000
lsof -i :8000
kill -9 <PID>

# Windows PowerShell:
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

### Frontend can't reach backend
- Check CORS_ALLOWED_ORIGINS in `backend/settings.py`
- Should include http://localhost:3000 for development

### Records appear in database but not in UI
- Refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
- Check browser console for errors (F12)
- Check backend logs: `python manage.py runserver` terminal

## 11. Next Steps

1. **Understand the data model**: Read `docs/MODEL.md`
2. **Review decisions**: Read `docs/DECISIONS.md`
3. **See what wasn't built**: Read `docs/TRADEOFFS.md`
4. **Learn source research**: Read `docs/SOURCES.md`
5. **Explore the code**: Start with `backend/views.py`

---

**Questions?** The documentation explains the "why" behind every design decision.
