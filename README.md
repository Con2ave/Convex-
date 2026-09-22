# ConVex

ConVex is a mobile-first study rewards application for students. Users complete verified study sessions, earn Knowledge Points (KP), track their progress, compare study streaks, and redeem eligible points for Ghana mobile-money rewards. The application also supports paid subscriptions, guided study sessions backed by uploaded material, and Google sign-in.

The repository contains a FastAPI backend and a React/Vite frontend. The original product and rollout assumptions are recorded in [study-rewards-app-architecture.md](study-rewards-app-architecture.md).

## What Is Implemented

- Account registration, password login, Google Identity Services login, email verification, password reset, logout, and refresh-token rotation.
- JWT-protected user and admin endpoints with role checks and rate limiting on sensitive authentication routes.
- Ordinary study sessions with start, pause, resume, heartbeat, anti-cheat checks, end-of-session summaries, and verified-minute accounting.
- Guided sessions that accept PDF or text material and generate a comprehension quiz asynchronously with Gemini.
- Knowledge Point ledger, streak bonuses, daily and weekly verified-minute caps, balance/history views, and fixed Ghana mobile-money redemption tiers.
- Monthly, quarterly, and annual subscriptions through Paystack checkout and server-side payment verification.
- Points and streak leaderboards.
- Responsive frontend pages for authentication, dashboard, active sessions, session history, quizzes, profile, subscriptions, settings, FAQ, and leaderboards.

## Architecture

```text
frontend/                 React 19 + TypeScript + Vite client
    |
    | HTTPS / REST with JWT bearer tokens
    v
auth-system/              FastAPI application
    |-- app/api/           HTTP route handlers
    |-- app/services/      Authentication, sessions, rewards, payments, quizzes
    |-- app/models/        SQLAlchemy database models
    |-- app/schemas/       Pydantic request and response models
    |-- app/crud/          Database access helpers
    |-- alembic/           Database migration history
    `-- tests/             Async integration and service tests
    |
    +-- SQLite locally or PostgreSQL in production
    +-- Paystack for subscriptions and real payouts
    +-- Gemini for guided-session quiz generation
    `-- SMTP or development log output for email flows
```

The backend normalizes hosted `postgres://` and `postgresql://` URLs to the async SQLAlchemy driver used by the application. Local development can use SQLite with `aiosqlite`.

## Repository Layout

```text
.
|-- auth-system/
|   |-- app/
|   |   |-- api/            FastAPI routers
|   |   |-- core/           Settings, database, security, rate limiting
|   |   |-- crud/           Async database queries
|   |   |-- dependencies/   Authentication and authorization dependencies
|   |   |-- models/         SQLAlchemy models
|   |   |-- schemas/        Pydantic schemas
|   |   `-- services/       Domain logic and external service clients
|   |-- alembic/            Migrations
|   |-- tests/              Backend test suite
|   |-- .env.example        Backend configuration template
|   |-- requirements.txt
|   `-- README.md            Backend-specific notes
|-- frontend/
|   |-- src/api/            Typed API client and frontend response types
|   |-- src/components/     Shared UI components
|   |-- src/context/        Authentication and theme state
|   |-- src/pages/          Routed application screens
|   |-- .env.example        Frontend configuration template
|   `-- package.json
|-- render.yaml             Render backend deployment definition
`-- study-rewards-app-architecture.md
```

## Requirements

- Python 3.12 recommended for the Render configuration.
- Node.js and npm compatible with the versions in `frontend/package.json`.
- SQLite for the default local database, or PostgreSQL for a production-like setup.
- Optional provider credentials for Google sign-in, Gemini quizzes, SMTP email, and Paystack.

## Local Setup

### 1. Configure the backend

From the repository root:

```powershell
cd auth-system
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `auth-system/.env` and replace at least these values before starting the API:

```env
JWT_SECRET_KEY=generate-a-long-random-secret
JWT_REFRESH_SECRET_KEY=generate-a-different-long-random-secret
DATABASE_URL=sqlite+aiosqlite:///./auth_system.db
ADMIN_PASSWORD=choose-a-strong-local-admin-password
```

The application seeds the configured admin account on startup using `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`. Do not use development credentials in a deployed environment.

For macOS/Linux, activate the environment with `source .venv/bin/activate` and copy the template with `cp .env.example .env`.

### 2. Apply migrations and start the API

Run these commands from `auth-system` with the virtual environment active:

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`.

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

### 3. Configure and start the frontend

Open a second terminal from the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The Vite development server normally runs at `http://localhost:5173`. The default frontend configuration points to `http://localhost:8000`; change `VITE_API_BASE_URL` when using another API host.

## Configuration

### Backend: `auth-system/.env`

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Yes | SQLite or PostgreSQL connection URL |
| `JWT_SECRET_KEY` | Yes | Access-token signing secret |
| `JWT_REFRESH_SECRET_KEY` | Yes | Refresh-token signing secret |
| `ADMIN_PASSWORD` | Yes | Password for the seeded administrator |
| `ADMIN_USERNAME`, `ADMIN_EMAIL` | No | Seeded administrator identity |
| `ALLOWED_ORIGINS` | No | Comma-separated frontend origins; defaults to local Vite |
| `FRONTEND_BASE_URL` | No | Paystack callback base URL |
| `PAYSTACK_SECRET_KEY` | No | Enables real subscription payments and MoMo payouts |
| `GEMINI_API_KEY` | No | Enables guided-session quiz generation |
| `GEMINI_MODEL` | No | Gemini model name; defaults to `gemini-flash-latest` |
| `GOOGLE_CLIENT_ID` | No | Enables backend Google ID-token verification |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | No | Sends email verification and reset links |

### Frontend: `frontend/.env`

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | No | Backend URL; defaults to `http://localhost:8000` |
| `VITE_GOOGLE_CLIENT_ID` | No | Shows the Google sign-in control when configured |

Unset optional integrations fail closed where appropriate. For example, guided sessions return an unavailable response without Gemini, and subscription checkout is unavailable without Paystack. Reward payouts use a logged mock provider locally when Paystack is unset.

## API Surface

All routes below are served by the backend at `http://localhost:8000`. Authenticated routes require a bearer access token unless stated otherwise.

| Group | Main operations |
| --- | --- |
| `/auth` | Register, login, Google login, logout, refresh, password reset, email verification |
| `/users` | Current profile and password updates |
| `/admin` | Admin user listing and deletion |
| `/study-sessions` | Start ordinary/guided sessions, heartbeat, pause/resume, checks, summaries, material, quizzes |
| `/rewards` | Balance, ledger, redemption tiers, MoMo redemption, redemption history |
| `/subscriptions` | Plans, status, Paystack initialization, verification, purchase history |
| `/leaderboard` | Points and consecutive-day streak rankings |
| `/health` | Deployment health check |

The complete request and response contract is available through the generated OpenAPI documentation at `/docs`.

## Reward Rules

- Study time is credited in 30-minute blocks at 10 KP per block.
- A perfect completed session can receive a 10 KP bonus, and the first completed session of a day can receive a 2 KP bonus.
- Consecutive-day streaks apply multipliers up to 2.5x.
- Guided sessions can earn an additional 2 KP target-time bonus when the target is met.
- Fixed redemption tiers are GHS 1 / 300 KP, GHS 2 / 600 KP, GHS 5 / 1,500 KP, and GHS 10 / 3,500 KP.
- Users may study and earn KP without subscribing, but an active subscription is required to redeem KP for cash. Administrators are exempt.

## Testing and Checks

Backend tests use an isolated SQLite database and mocked external integrations:

```powershell
cd auth-system
.venv\Scripts\Activate.ps1
python -m pytest -v
```

Frontend checks and production build:

```powershell
cd frontend
npm run lint
npm run build
```

## Deployment

`render.yaml` defines the backend deployment on Render. It installs Python dependencies, runs `alembic upgrade head`, starts Uvicorn, and checks `/health`. Configure the secret and provider values marked `sync: false` in Render, including `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `PAYSTACK_SECRET_KEY`, `FRONTEND_BASE_URL`, and `ALLOWED_ORIGINS`.

The frontend is a standard Vite build and can be deployed to Vercel or another static hosting provider. Set `VITE_API_BASE_URL` to the deployed API URL and add the deployed frontend URL to the backend's `ALLOWED_ORIGINS`.

For production, use PostgreSQL with persistent storage for uploaded guided-session material, strong unique secrets, HTTPS, real SMTP credentials, and real Paystack credentials. The current payout reconciliation path can leave a production transfer in `pending` when the provider does not confirm it during the short polling window; operational reconciliation is still required for such cases.

## Development Notes

- Run Alembic commands from `auth-system`, where `alembic.ini` and the application package are located.
- Do not commit `.env` files, database files, uploaded materials, or provider secrets.
- The frontend stores access and refresh tokens in browser local storage and automatically attempts refresh-token rotation after an unauthorized API response.
- The project is currently a web-first implementation of the product architecture; a native mobile client is not included in this repository.
