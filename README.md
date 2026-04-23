# LynxHealth
An app for Rhodes Health Center

## Prerequisites & Environment

- Python 3.10+ (the backend uses modern type syntax such as `str | None`)
- Node.js compatible with Angular 21 (the frontend currently uses `npm@11.6.2`)
- A running PostgreSQL database
- (Optional but recommended) a local virtual environment at `.venv/` for Python dependencies

### Required environment variable

Set `DATABASE_URL` so FastAPI can connect to Postgres (loaded from environment via `python-dotenv`):

```bash
export DATABASE_URL="postgresql://lynx-health:Oc9mox$ZeukKL2Iu@34.122.29.113:5432/lynx-health"
```

Without a valid `DATABASE_URL`, backend startup and API calls will fail database checks.

### SAML settings

SAML configuration is read from:

```text
backend/saml/settings.json
```

For SSO environments, make sure the `sp` and `idp` settings in that file match your deployment URLs and IdP metadata.

## Running the App

Start from the project root:

### Windows

Use PowerShell:

```powershell
.\start.ps1
```

If PowerShell blocks the script, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start.ps1
```

What this script does:
- activates the Python virtual environment if `.venv` exists
- starts the frontend from `frontend`
- starts the FastAPI backend on `http://localhost:8000`

### macOS or Linux

```bash
./start.sh
```

If needed, make it executable first:

```bash
chmod +x ./start.sh
./start.sh
```

### First-time setup

If startup fails because dependencies are missing:

```bash
pip install -r requirements.txt
cd frontend
npm install
```

## Local Authentication Modes

### 1) SSO mode (real auth flow)
- Use the login page SSO action, which calls `GET /api/auth/sso/login`.
- The backend redirects to the IdP and receives the assertion at the callback endpoint.
- After successful auth, backend redirects to `/home` with a session payload that the frontend stores in `localStorage` as `lynxSession`.

### 2) Local test mode (no IdP required)
- The login page includes test admin and test user actions for local development.
- These actions write a local mock session directly (no backend SAML round-trip).
- Use this mode when SAML is unavailable and you still need to test role-specific UI behavior.

## Technologies we used

Languages: Python, SQL, Typescript, HTML, CSS
Technologies: GitHub, Trello and Google Drive (for planning)
Personal tools: Visual Studio Code, PyCharm
AI Usage: Codex, Claude

## API Summary

Backend base URL in local dev: `http://localhost:8000`  
Frontend commonly calls these through `/api/...` proxy routes.

Role checks are currently enforced by email convention in request payload/query params (`@admin.edu` for admins).

## Project Structure

```text
LynxHealth/
├── backend/
│   ├── main.py                   # FastAPI app entry, middleware, router registration
│   ├── database.py               # SQLAlchemy engine/session + schema/index checks
│   ├── routes/
│   │   ├── auth_routes.py        # SAML login/callback endpoints
│   │   ├── availability_routes.py# Scheduling, clinic hours, appointment APIs
│   │   └── page_routes.py        # Editable page content APIs
│   ├── models/                   # ORM models (appointments, availability, hours, etc.)
│   └── saml/settings.json        # SAML SP/IdP config used by auth routes
├── frontend/
│   ├── src/app/
│   │   ├── login/                # Login + SSO/test-login entry points
│   │   ├── availability-calendar/# Student booking flow
│   │   ├── my-appointments/      # Student manage/reschedule/cancel flow
│   │   ├── create-appointments/  # Admin scheduling controls
│   │   ├── hours/                # Clinic hours + holiday management
│   │   └── resources/            # CMS-like editable resources page
│   ├── proxy.conf.json           # /api -> backend proxy for local dev
│   └── package.json              # Angular scripts/dependencies
├── tests/backend/routes/         # Backend route tests
├── start.sh                      # Unix startup script (frontend + backend)
├── start.ps1                     # Windows startup script (frontend + backend)
├── requirements.txt              # Python dependencies
└── README.md
```

## How the Project Works

### 1) System architecture
- The frontend is an Angular app in `frontend/` with route-based pages (`login`, `home`, `hours`, `create-appointments`, `availability-calendar`, `my-appointments`, and `resources`).
- The backend is a FastAPI app in `backend/` with three main route groups:
  - `/auth` for SAML login/callback
  - `/availability` for clinic hours, appointment types, slot generation, and appointment operations
  - `/pages` for editable resources-page content
- Data is stored with SQLAlchemy models (`appointments`, `availability`, `appointment_type_options`, `clinic_hours`, `clinic_holidays`, `page_sections`, and users). On backend startup, tables are created if missing and schema/index checks are applied.

### 2) Local runtime flow
- `./start.sh` (macOS/Linux) and `.\start.ps1` (Windows) start both apps:
  - Angular dev server on `http://localhost:4200`
  - FastAPI on `http://localhost:8000`
- During frontend development, requests to `/api/*` are proxied to `http://localhost:8000` and rewritten to backend paths.
- Most frontend API calls use `/api/...`. The resources page component currently calls `http://localhost:8000/pages/...` directly.

### 3) Authentication and session flow
- Login starts at `/api/auth/sso/login`, which redirects to SAML IdP login.
- The backend SAML callback reads attributes (`Email`, `FirstName`, `LastName`) and infers role from email:
  - `@admin.edu` => `admin`
  - everything else => `user`
- The callback redirects with an encoded `session` payload in the URL.
- The frontend `home` page parses that payload and saves a normalized session in `localStorage` (`lynxSession`), which all pages use for role-based behavior and request email values.

### 4) Scheduling workflow (core app behavior)
- Admin workflows:
  - manage clinic hours and holidays (`GET/PUT /availability/clinic-hours`)
  - block and unblock individual time slots (`POST/DELETE /availability/slots`)
  - create and remove appointment types (`GET/POST/DELETE /availability/appointment-types`)
  - view all upcoming booked appointments (`GET /availability/appointments`)
- Student workflows:
  - browse generated available slots by appointment type (`GET /availability/calendar`)
  - book an appointment (`POST /availability/appointments`)
  - manage their appointments (`GET /availability/appointments/mine`, `PATCH .../reschedule`, `PATCH .../notes`, `DELETE ...`)
  - download `.ics` files for calendar import (`GET /availability/appointments/{id}/ics`)
- The backend enforces scheduling rules (open days/hours, 15-minute boundaries, lunch-hour block, no overlap with blocked times/booked appointments, and role checks by email).

### 5) Resources page content management
- The resources page is backed by `page_sections` records and `backend/routes/page_routes.py`.
- `GET /pages/{page}/sections` seeds default resources content if nothing exists yet.
- Admins can bulk update, add, and delete sections via `/pages/{page}/sections` endpoints, and the frontend editor reflects those persisted sections.

## Planning

[Google Drive](https://drive.google.com/drive/u/1/folders/1ygJ4fZOfbDO0bYAbOHXsf_lC90die02E)
[Trello](https://trello.com/invite/b/697001788efc1defe5a3c0e6/ATTIee4065e776be3bd7c7b64f4d1da0c7a9BC3157F0/comp486)

## Testing

### Backend unit tests
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run tests:
   ```bash
   pytest
   ```
