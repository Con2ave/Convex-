# FastAPI Production-Ready Authentication System

A secure, modular, production-ready authentication and authorization system built with **FastAPI**, **SQLAlchemy 2.0**, **Alembic**, and **Pydantic v2**. 

## Kept Design Standards & Architectural Decisions

1. **Database Modularity (SQLite to PostgreSQL)**:
   - Built around SQLAlchemy 2.0 async engines (`aiosqlite`). 
   - Swapping to PostgreSQL requires zero code changes; simply edit the `DATABASE_URL` in `.env` to point to a `postgresql+asyncpg://...` connection string.
2. **Refresh Token Rotation (RTR)**:
   - Validating a refresh token revokes it and issues a newly calculated access/refresh pair, securing endpoints against replay attacks.
   - Built-in reuse detection auto-revokes all user tokens if an invalid/old refresh token is submitted twice.
3. **Stateless Scope-based JWTs**:
   - Password reset and email verification flows are stateless. Tokens are signed JWTs containing unique claims/scopes (`password_reset`, `email_verification`), reducing unnecessary database indexing read operations.
4. **Dependency-based Role Access Control (RBAC)**:
   - Implements a parameterized dependency class `RoleChecker(["admin", "user"])` generating granular access policies and reflecting role locks nicely in Swagger UI.
5. **Brute Force Defense**:
   - Integrates IP-based Rate Limiting on critical entry points (register, login, password reset) using `slowapi`.

---

## Project Structure

```text
auth-system/
│
├── app/
│   ├── main.py             # App initialization, CORS, Lifespan Seeding, exceptions
│   ├── core/
│   │     config.py         # Pydantic v2 BaseSettings environment validation
│   │     security.py       # Hashing and JWT token generation tools
│   │     database.py       # Engine binding and context get_async_db yields
│   │     limiter.py        # Throttling instance configuration
│   │
│   ├── models/
│   │     __init__.py
│   │     user.py           # User and UserRefreshToken db schemas
│   │
│   ├── schemas/
│   │     user.py           # Strong validation request/response schemas
│   │
│   ├── crud/
│   │     __init__.py
│   │     user.py           # SQL queries using SQLAlchemy 2.0 Async format
│   │
│   ├── api/
│   │     auth.py           # Authentication endpoints (login, register...)
│   │     users.py          # User setting edits and admin controllers
│   │
│   └── dependencies/
│         __init__.py
│         auth.py           # JWT payload decoders and RBAC classes
│
├── tests/
│     conftest.py           # Async fixtures, database drop/creates, and mock clients
│     test_auth.py          # 13 integration test covers
│
├── alembic/                # Migration revisions history
│
├── requirements.txt        # Package configuration list 
├── pytest.ini              # Async test configs
├── .env                    # Active configurations file
├── .env.example            # Environment variables template
└── README.md
```

---

## API Endpoints

### 🔐 Authentication (`/auth`)
* `POST /auth/register` - Registers a new user. Emits a mock email token in the logging terminal.
* `POST /auth/login` - Form-based OAuth2 login returning access + refresh tokens.
* `POST /auth/logout` - Revokes/invalidates current refresh token in database.
* `POST /auth/refresh` - Employs refresh token rotation returning a new set of JWTs.
* `POST /auth/forgot-password` - Requests reset email. Emits mock code in logs securely.
* `POST /auth/reset-password` - Resets password via validation token. Clears outstanding active user sessions in DB.
* `GET /auth/verify-email` - Confirms registration email verification.

### 👤 Profile settings (`/users`)
* `GET /users/me` - Retrieves profile details for the logged-in User.
* `PUT /users/me` - Updates metadata (email, username). Resetting verification state if email changes.
* `PUT /users/change-password` - Securely changes user password, revoking outstanding login sessions.

### 🛡️ Administration (`/admin`, Admin-only)
* `GET /admin/users` - Lists all registered user accounts (paginated).
* `DELETE /admin/users/{id}` - Deletes a user account. Incorporates safety guards against admin self-deletion.

---

## Getting Started

### 1. Installation
Clone the repository and prepare a Python virtual environment:
```bash
# Create Virtual Environment
python -m venv .venv

# Activate Virtual Environment
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` as `.env` and fill in secrets:
```bash
cp .env.example .env
```

### 3. Run Database Migrations
Initialize database tables via Alembic:
```bash
alembic upgrade head
```

### 4. Running the Dev Server
Launch the ASGI local server:
```bash
uvicorn app.main:app --reload
```
Navigate to [http://localhost:8000/docs](http://localhost:8000/docs) to access the interactive Swagger OpenAPI system docs!
On startup, a default administrator is seeded according to `.env` configurations:
* **Admin Username**: `admin`
* **Admin Email**: `admin@example.com`
* **Admin Password**: `SuperSecurePassword123!`

---

## Troubleshooting & Running Tests

Execute the asyncio test suite via pytest:
```bash
python -m pytest -v
```

---

## Transitioning to PostgreSQL in Production
To swap from local SQLite to PostgreSQL, perform the following setup steps:
1. Install PostgreSQL adapter in your environment:
   ```bash
   pip install asyncpg psycopg2-binary
   ```
2. Update `DATABASE_URL` in your active `.env` file:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres_user:postgres_pass@localhost:5432/postgres_db
   ```
3. Run migrations on the new database:
   ```bash
   alembic upgrade head
   ```
4. Start your server. The application will dynamically interface with PostgreSQL using the exact same code structure.
