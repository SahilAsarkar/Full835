# OneSmarter Admin Portal — MIR Relay Compliance & Onboarding

Enterprise Admin UI and Backend for tracking client onboarding evidence (NDAs, BAAs, HIPAA/SOC2 compliance, 835 EDI test files) across a sequential 15-step compliance ladder.

---

## 🚀 Active Tech Stack

The production-ready active stack consists of:
- **Frontend**: React 18 SPA built with Vite (`frontend_react/`), styled with vanilla CSS design system tokens.
- **Backend**: Django 6.1 REST Framework (`django_backend/`) with relational SQLite / PostgreSQL database support.
- **Test Suite**: Django automated test runner (`run_django_tests.py`) covering 19 comprehensive unit and integration tests.

---

## 🏃 Running the Application

### Option A: One-Click Launcher (Windows)

Simply double-click **`run_portal.bat`** (or run `.\run_portal.bat` from PowerShell/cmd). It will:
1. Verify Python and Node.js environments.
2. Install any missing Python/npm dependencies.
3. Apply database migrations and seed default data.
4. Launch the Django backend (`:8000`) and Vite React frontend (`:5173`).
5. Open your default web browser to the admin portal.

---

### Option B: Manual Execution

```bash
# 1. Start Django Backend (Port 8000)
cd django_backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver 127.0.0.1:8000

# 2. Start React Frontend (Port 5173) in a separate terminal
cd ../frontend_react
npm install
npm run dev
```

Then navigate to **http://localhost:5173/** in your browser.

- **Default Admin Credentials**:
  - **Username**: `admin`
  - **Password**: `adminpassword`

---

## 🔐 Authentication & Security

- **Auth Mechanism**: `POST /api/auth/login/` returns a Bearer token.
- **Token Enforcement**: All protected `/api/*` endpoints require `Authorization: Bearer <token>` in HTTP headers. Unauthenticated requests receive `401 Unauthorized`.
- **Action Type Verification**: Step upload endpoints verify that `action_type` accepts file uploads (`upload_template`, `email_upload`, `x12_835_validate`) before accepting files.
- **Upload Size Limit**: Uploads on `/api/clients/{id}/steps/{key}/upload` are capped at **10 MB** (returns `413 Payload Too Large` if exceeded).
- **XSS Protection**: HTML escaping applied to user inputs and X12 EDI validation outputs.
- **Production Checklist Notes**:
  - `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=False` must be configured in environment variables prior to production deployment.
  - CORS settings in `settings.py` should be restricted from open reflection to specified domain origins.

---

## ⚙️ Environment Variables (Configuration)

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(insecure demo key)* | Secret key for Django cryptographic signing |
| `DJANGO_DEBUG` | `true` | Toggle Django debug mode |
| `USE_POSTGRES` | `false` | Set to `true` to use PostgreSQL instead of SQLite |
| `POSTGRES_DB` | `onesmarter_db` | PostgreSQL database name |
| `POSTGRES_USER` | `postgres` | PostgreSQL user |
| `POSTGRES_PASSWORD` | `postgres` | PostgreSQL password |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost,*` | Django allowed hosts |
| `RETENTION_DAYS` | `365` | Retention window (days) for evidence cleanup |

---

## 🧪 Running Automated Tests

```bash
# Run Django REST Framework backend test suite (43 tests)
python run_django_tests.py
```
