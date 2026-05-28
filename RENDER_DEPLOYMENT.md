# Deploying BreatheESG to Render

This guide walks you through deploying the BreatheESG platform to Render.com with a free tier setup.

## Prerequisites

1. **GitHub Account** (to push your code)
2. **Render Account** (free at https://render.com)
3. **Project pushed to GitHub** (Render deploys from Git)

## Step 1: Push Project to GitHub

```bash
# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: BreatheESG platform"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/BreatheESG.git

# Push to main branch
git branch -M main
git push -u origin main
```

## Step 2: Create Render Account & Connect GitHub

1. Go to https://render.com
2. Sign up with GitHub account
3. Click "Connect GitHub" when prompted
4. Authorize Render to access your repositories

## Step 3: Deploy Backend (Django API)

### 3a. Create Web Service

1. Go to **Dashboard** → **New** → **Web Service**
2. Select your **BreatheESG** repository
3. Fill in the following:

| Setting | Value |
|---------|-------|
| Name | `breathe-esg-backend` |
| Environment | `Python 3` |
| Build Command | `pip install -r backend/requirements.txt && python backend/manage.py collectstatic --no-input` |
| Start Command | `gunicorn -w 4 -b 0.0.0.0:$PORT backend.wsgi:application` |
| Plan | `Free` |

### 3b. Add Environment Variables

After service creation, go to **Environment** tab and add:

```
DEBUG=false
SECRET_KEY=generate-a-long-random-string-here
DATABASE_URL=postgresql://user:password@host/dbname (auto-filled if you create DB)
ALLOWED_HOSTS=your-backend-domain.onrender.com
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.onrender.com
FRONTEND_URL=https://your-frontend-domain.onrender.com
```

**To generate SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3c. Create Database

1. Go to **Dashboard** → **New** → **PostgreSQL**
2. Fill in:

| Setting | Value |
|---------|-------|
| Name | `breathe-esg-db` |
| Database | `breatheesg` |
| User | `breatheesg_user` |
| Plan | `Free` |
| Region | `Oregon` (or your preferred) |

3. Copy the **Internal Database URL** (this auto-fills into backend service)
4. Click **Create Database**

### 3d. Connect Database to Backend

1. Go back to your **breathe-esg-backend** service
2. Go to **Environment**
3. The `DATABASE_URL` should already be populated
4. If not, paste the database URL you just created

## Step 4: Deploy Frontend (React)

### 4a. Create Static Site

1. Go to **Dashboard** → **New** → **Static Site**
2. Select your **BreatheESG** repository
3. Fill in:

| Setting | Value |
|---------|-------|
| Name | `breathe-esg-frontend` |
| Build Command | `cd frontend && npm install && npm run build` |
| Publish Directory | `frontend/build` |
| Plan | `Free` |

4. Click **Create Static Site**

### 4b. Update Frontend API URL

After frontend is deployed, go to **frontend/src/App.js** and update the API URL:

```javascript
// Replace localhost with your backend domain
const API_BASE_URL = 'https://your-backend-domain.onrender.com';
```

Then push to GitHub:
```bash
git add frontend/src/App.js
git commit -m "Update API URL for production"
git push
```

The frontend will auto-deploy when you push.

## Step 5: Test Your Deployment

### 5a. Get Your Domains

1. Backend: Go to **breathe-esg-backend** service → Copy domain (e.g., `https://breathe-esg-backend-xxxxx.onrender.com`)
2. Frontend: Go to **breathe-esg-frontend** site → Copy domain (e.g., `https://breathe-esg-frontend-xxxxx.onrender.com`)

### 5b. Test API

```bash
# Test if backend is running
curl https://your-backend-domain.onrender.com/api/records/

# Should return: {"count": 0, "results": []}
```

### 5c. Test Frontend

Open `https://your-frontend-domain.onrender.com` in browser. You should see the upload form.

### 5d. Test Upload

1. Upload a CSV file from `sample_data/`
2. Check if records appear
3. Try to approve/lock records

## Step 6: Update Settings

### Update Backend CORS & Hosts

1. Go to **breathe-esg-backend** → **Environment**
2. Update these variables with your actual domains:

```
ALLOWED_HOSTS=breathe-esg-backend-xxxxx.onrender.com
CORS_ALLOWED_ORIGINS=https://breathe-esg-frontend-xxxxx.onrender.com
FRONTEND_URL=https://breathe-esg-frontend-xxxxx.onrender.com
```

3. Click **Save**
4. Service will auto-restart

### Update Frontend API URL

Update **frontend/src/App.js**:

```javascript
const API_BASE_URL = 'https://breathe-esg-backend-xxxxx.onrender.com';
```

Commit and push:
```bash
git add frontend/src/App.js
git commit -m "Update API URL to production backend"
git push
```

## Step 7: Continuous Deployment

Now whenever you push to GitHub:
- ✅ Backend auto-deploys if `backend/` files change
- ✅ Frontend auto-deploys if `frontend/` files change
- ✅ Database persists across deployments

To trigger a re-deployment manually:
1. Go to service
2. Click **Manual Deploy** → **Deploy latest commit**

## Troubleshooting

### Backend gives "502 Bad Gateway"

**Check logs:**
1. Go to service
2. Click **Logs** tab
3. Look for error messages

Common issues:
- `ModuleNotFoundError`: Requirements not installed → check `backend/requirements.txt`
- `ImportError`: Database URL not set → check Environment variables
- `DisallowedHost`: ALLOWED_HOSTS doesn't match → update in Environment

### Frontend is blank

**Check browser console:**
1. Open DevTools (F12)
2. Go to Console tab
3. Look for errors

Common issues:
- `CORS error`: Backend domain not in CORS_ALLOWED_ORIGINS
- `Cannot GET /`: Frontend build failed → check build command
- `Failed to fetch from API`: API_BASE_URL wrong → update in App.js

### Database won't connect

**Check connection string:**
1. Go to PostgreSQL service → **Connect**
2. Copy Internal Database URL
3. Paste into Backend Environment as `DATABASE_URL`
4. Trigger re-deploy

### Emails/Logs not showing

Free tier has limited log retention (~1 hour). To increase:
1. Upgrade to paid plan
2. Or check logs immediately after issue occurs

## Free Tier Limits (Important!)

| Resource | Free Tier | Upgrade |
|----------|-----------|---------|
| Backend Services | 1 | Many |
| Static Sites | 2 | Unlimited |
| Databases | 1 | Many |
| Disk | 0.5 GB | More |
| RAM | 512 MB | 1-4 GB |
| CPU | Shared | Dedicated |
| Auto-sleep | Yes (after 15 min) | No |

⚠️ **Warning**: Free tier services sleep after 15 minutes of inactivity. First request takes ~30 seconds to wake up.

**To avoid sleep:**
- Upgrade to paid plan
- OR use a monitoring service to ping periodically

## Cost Estimate

| Service | Free | Paid |
|---------|------|------|
| Backend | Free | $7/mo |
| Frontend | Free | $0 (included) |
| Database | Free | $9/mo |
| **Total** | **$0** | **~$16/mo** |

## Next Steps

1. ✅ Deploy backend
2. ✅ Deploy frontend
3. ✅ Test upload workflow
4. ✅ Invite team members
5. ⏭️ Consider upgrading to paid ($16/mo) for production use

## Sample Domain Names

Your domains will look like:
- Backend: `https://breathe-esg-backend-a1b2c3d4e5f6.onrender.com`
- Frontend: `https://breathe-esg-frontend-a1b2c3d4e5f6.onrender.com`

You can add custom domains later if you own a domain.

## Need Help?

- **Render Docs**: https://render.com/docs
- **Django Deployment**: https://docs.djangoproject.com/en/4.2/howto/deployment/
- **React Build**: https://create-react-app.dev/docs/deployment/

## Keeping Deployment Updated

When you update your code:

```bash
# Make changes locally
git add .
git commit -m "Your change description"
git push origin main

# Render will auto-deploy!
# Check deployment status in Render Dashboard
```

No manual re-deployment needed—Render watches your GitHub repo and deploys automatically.
