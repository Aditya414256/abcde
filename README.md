# MediFind — Medicine Availability & Verified Pharmacy Locator

MediFind is a full-stack healthcare web application that connects customers with local pharmacies. Customers search for medicines by name or generic name, find pharmacies with available stock, and choose between **Store Pickup** or **Home Delivery**. Pharmacy owners manage their inventory, orders, and prescriptions through a dedicated portal. Admins verify pharmacy registrations and manage platform health.

---

## Main Features

### Customer
- Live autocomplete medicine search (name & generic name)
- Browse the full active pharmacy directory
- Store Pickup: view all eligible pharmacies with stock, select preferred store, place order
- Home Delivery: view delivery-enabled pharmacies, submit address, upload prescription when required
- Order history & status tracking
- Medicine availability requests (notify pharmacy when medicine is out of stock)
- In-app notifications (order placed, accepted, rejected, status changes, request updates)
- Cancel orders in PENDING or ACCEPTED state
- Prescription upload to private Supabase Storage bucket with local fallback
- Profile management (update full name and change password)

### Pharmacy Owner
- Dashboard with incoming orders (PENDING → ACCEPTED → CONFIRMED → PREPARING → READY/OUT → COMPLETED)
- Inventory management (add/update medicines, quantities, prices, batch numbers, expiry dates)
- Manual prescription review for Home Delivery orders
- Physical prescription verification protocol for Store Pickup orders (verified at counter)
- Upload pharmacy verification documents (drug license) to private Supabase Storage
- Review and update customer medicine availability requests (PENDING → ACKNOWLEDGED → FULFILLED / REJECTED)
- In-app notifications for new orders, customer requests, and verification updates

### Admin
- Review pharmacy registration documents (streamed securely from Supabase Storage)
- Approve or reject pharmacy verification
- Manual prescription review permissions
- Toggle pharmacy active/inactive status
- Platform metrics dashboard

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, Vanilla CSS3, Vanilla JavaScript (ES6+) |
| Backend | Python 3, Flask 3, Flask-Login, Flask-SQLAlchemy, Flask-Migrate |
| Database | SQLite (development) / PostgreSQL via Supabase (production) |
| Migrations | Alembic (via Flask-Migrate) |
| Testing | pytest |
| Deployment | Vercel (serverless, Python runtime) |

---

## Application Architecture

```
backend/
├── app.py               # Flask application factory (registers blueprints, Flask-Migrate)
├── config.py            # Config classes: Config, DevelopmentConfig, ProductionConfig, TestingConfig
├── database.py          # SQLAlchemy db instance
├── models.py            # SQLAlchemy models: User, Pharmacy, Medicine, PharmacyInventory,
│                        #   Prescription, Order, Notification, MedicineRequest
├── seed.py              # Database seed + schema migration helper
├── routes/
│   ├── auth_routes.py         # /api/auth/* — register, login, logout, current-user, profile
│   ├── medicine_routes.py     # /api/medicines/* — search, suggestions, detail
│   ├── order_routes.py        # /api/orders/* — pickup, delivery, status, idempotency
│   ├── pharmacy_routes.py     # /api/pharmacies, /api/pharmacy/* — directory, orders, inventory, docs
│   ├── admin_routes.py        # /api/admin/* — verification, prescription review, stats
│   ├── notification_routes.py # /api/notifications, /api/prescriptions/*
│   └── request_routes.py      # /api/requests, /api/pharmacy/requests — medicine availability requests
└── services/
    ├── order_service.py            # Core order business logic, state machine, stock rules
    ├── pharmacy_service.py         # Pharmacy registration, verification, listing
    ├── inventory_service.py        # Inventory CRUD, non-negative enforcement
    ├── prescription_service.py     # Secure upload, access control, manual review
    ├── supabase_storage_service.py # Supabase Storage integration (prescriptions, pharmacy-docs)
    ├── request_service.py          # Medicine availability request workflow
    ├── notification_service.py     # In-app notification creation and retrieval
    ├── medicine_service.py         # Search and autocomplete
    └── location_service.py         # Haversine distance calculation

frontend/
├── HomePage.html/css       # Customer home with medicine autocomplete
├── FindMedi.html           # Medicine search results and ordering flow
├── Pharmacies.html/css     # Public pharmacy directory
├── login.html              # Login page
├── register*.html          # Customer and pharmacy registration
├── pharmacy-dashboard.html # Pharmacy owner portal
├── admin-dashboard.html    # Admin portal
└── js/                     # Modular ES6 scripts (api.js, auth.js, selection.js, etc.)

tests/
├── test_medifind.py        # Main pytest suite (70 tests: security, state machine, requests, profile)
├── test_supabase_storage.py# Supabase Storage integration tests (5 tests: upload, download, sign, delete)
├── test_pg_concurrency.py  # PostgreSQL-only concurrency safety tests
├── verify_supabase_db.py   # PostgreSQL connection and dialect diagnostic
└── apply_pg_schema.py      # Supabase PostgreSQL schema initialization and Alembic stamper

api/
└── index.py                # Vercel serverless entry point

migrations/                 # Alembic migration files (managed by Flask-Migrate)
```

---

## User Roles

| Role | Email (demo) | Password | Capabilities |
|---|---|---|---|
| Customer | `customer@example.com` | `customer123` | Search, order, track, cancel, upload prescriptions |
| Ram Medical | `ram@pharmacy.com` | `pharmacy123` | Manage orders, inventory, review prescriptions |
| Shree Ji Medical | `shreeji@pharmacy.com` | `pharmacy123` | Same as above |
| Tasir Medical | `tasir@pharmacy.com` | `pharmacy123` | Same as above |
| Shree Gangai Medical | `gangai@pharmacy.com` | `pharmacy123` | Same as above |
| Admin | `admin@medifind.com` | `admin123` | Verify pharmacies, manage platform |

---

## Customer Workflow

1. Search for a medicine on the Home page.
2. Choose **Take From Store** (Pickup) or **Take From Delivery**.
3. **Store Pickup**: Browse eligible pharmacies with available stock → select pharmacy → review order → confirm.
4. **Home Delivery**: Browse delivery-enabled pharmacies → enter address → upload prescription if required → confirm.
5. Track order status in My Orders / notifications.
6. Cancel in PENDING or ACCEPTED state.

---

## Pharmacy Workflow

1. Register pharmacy → submit for admin verification.
2. Once verified, manage inventory (add medicines, set prices, update stock).
3. Incoming orders appear as PENDING.
4. Accept order → Confirm (triggers stock deduction) → Mark Preparing → Ready/Out for delivery → Complete.
5. Reject order with reason → customer notified ("Your order was not taken.").
6. For Store Pickup Rx orders: verify physical prescription at counter before dispensing.
7. For Home Delivery Rx orders: review uploaded prescription → approve/reject before confirming.

---

## Admin Workflow

1. Review pending pharmacy registrations in Admin Portal.
2. Approve (pharmacy becomes visible in Store Pickup/Delivery search) or reject.
3. Toggle pharmacy active/inactive without changing verification status.
4. View platform statistics.

---

## Order Lifecycle

```
PENDING → ACCEPTED → CONFIRMED → PREPARING → READY_FOR_PICKUP / OUT_FOR_DELIVERY → COMPLETED
                ↘ REJECTED
                                        ↘ CANCELLED (by pharmacy or admin)
                                CANCELLED (by customer — PENDING or ACCEPTED only)
```

### Customer cancellation rules
- **PENDING**: Customer can cancel. No stock was deducted. No stock change on cancellation.
- **ACCEPTED**: Customer can cancel. No stock was deducted yet. No stock change on cancellation.
- **CONFIRMED or later**: Customer **cannot** cancel. The order is being prepared.

---

## Inventory Rules

| Event | Stock Change |
|---|---|
| Order created (PENDING) | **No change** |
| ACCEPTED | **No change** |
| ACCEPTED → CONFIRMED | **Deducted once** (atomic, row-level lock) |
| CONFIRMED → CANCELLED/REJECTED | Restored once |
| PENDING/ACCEPTED → CANCELLED/REJECTED | No change (nothing was deducted) |
| Order COMPLETED | No change (already deducted at CONFIRMED) |

Stock never goes negative. Insufficient stock at CONFIRMED time prevents confirmation.

---

## Prescription Workflow

### Store Pickup
- Digital upload **not required**.
- The `prescription_pending_at_pickup=True` flag is set automatically.
- Pharmacy **must** verify the physical prescription at the counter before dispensing.

### Home Delivery
- Prescription-required medicines **require a digital upload** before the order can be placed.
- Prescription starts in `PENDING` status after upload.
- Pharmacy manually reviews and approves or rejects.
- **Rejection requires a reason**. Rejected prescription automatically rejects related PENDING delivery orders and notifies the customer.
- Prescription approval is **separate** from order acceptance. The pharmacy must still accept the order after approving the prescription.
- Prescription files are never publicly accessible — all downloads require authentication and ownership checks.

---

## Local Installation

### Prerequisites
- Python 3.10+

### Setup

```bash
# Clone the repository
git clone https://github.com/Aditya414256/Medi-Finder.git
cd Medi-Finder

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env
# Edit .env if needed (SQLite default works out of the box)

# Run the application
python run.py
```

Server starts at: **http://127.0.0.1:5000**

The database (`medifind.db`) is automatically seeded with pharmacies, medicines, and inventory on first run.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | **Production** | Long random string. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_ENV` | Optional | `development` (default) or `production` |
| `DATABASE_URL` | Production | PostgreSQL connection string (Supabase transaction pooler) |
| `MIGRATION_DATABASE_URL` | Production | PostgreSQL direct URL for migrations (not the pooler) |
| `SUPABASE_URL` | Production | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Production | Server-side only. Never expose to browser |
| `SUPABASE_PRESCRIPTIONS_BUCKET` | Production | Private Supabase Storage bucket name |
| `TEST_DATABASE_URL` | PG tests | Local test PostgreSQL URL (must contain 'test' in DB name, host must be localhost) |

---

## SQLite Setup (Development)

No setup required. The application automatically creates `medifind.db` and seeds it on first run.

```bash
python run.py
```

---

## Supabase PostgreSQL Setup (Production)

1. Create a Supabase project at https://supabase.com
2. Note your **Transaction Pooler** URL (port 6543) — use this for `DATABASE_URL` (Vercel/serverless)
3. Note your **Direct** database URL (port 5432) — use this for `MIGRATION_DATABASE_URL` (migrations only)
4. Set environment variables:
   ```
   DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@<pooler-host>:6543/postgres?sslmode=require
   MIGRATION_DATABASE_URL=postgresql+psycopg2://postgres:<password>@<db-host>:5432/postgres?sslmode=require
   SECRET_KEY=<long-random-string>
   FLASK_ENV=production
   ```
5. Install psycopg2: `pip install psycopg2-binary`

> **Note:** Supabase's transaction pooler uses PgBouncer, which does not support PostgreSQL prepared statements. SQLAlchemy is configured to handle this correctly via `pool_pre_ping` and connection settings.

---

## Supabase Storage Setup (Production)

Prescription files and pharmacy license documents are stored in **private** Supabase Storage buckets, not on the Vercel serverless filesystem (ephemeral) and never in public buckets.

1. **Storage Buckets:**
   - `prescriptions` — customer prescription uploads (private)
   - `pharmacy-docs` — pharmacy verification documents (private)
   Both buckets are automatically created and configured with `public = false`.
2. **Environment Variables:**
   ```env
   SUPABASE_URL=https://<project-ref>.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
   SUPABASE_PRESCRIPTIONS_BUCKET=prescriptions
   SUPABASE_PHARMACY_DOCS_BUCKET=pharmacy-docs
   ```
3. **Security Architecture:**
   - The service-role key is kept **strictly server-side** in `.env` (never exposed to the browser).
   - All prescription and document downloads are checked via role-based access control before streaming file bytes.
   - Offline / local fallback is built-in: if Supabase credentials are not configured, files seamlessly fall back to local disk storage (`uploads/`).

**Current status:** ✅ **Supabase Storage integration is fully implemented and tested.** Both `prescriptions` and `pharmacy-docs` buckets are active. Uploads, downloads, streaming, and signed URLs are live.

---

## Migration Commands

### Initialize (first time only — already done)
```bash
flask db init
```

### Generate a new migration after model changes
```bash
flask db migrate -m "describe your change"
# Review the generated file in migrations/versions/
flask db upgrade
```

### Apply migrations (development)
```bash
flask db upgrade
```

### Apply migrations (production — use direct URL, not pooler)
```bash
$env:DATABASE_URL = $env:MIGRATION_DATABASE_URL
flask db upgrade
```

### Rollback one migration
```bash
flask db downgrade
```

### Rollback to base (removes all tables — use with extreme caution)
```bash
flask db downgrade base
```

> **Critical:** Never run `flask db downgrade base` against a production database without a backup and explicit plan. Always verify migrations on a disposable database first.

---

## Test Commands

### Run the full test suite
```bash
python -m pytest tests/test_medifind.py tests/test_supabase_storage.py -v
```

Expected: **74 passed, 1 skipped** (100% passing)

### Run a specific test
```bash
python -m pytest tests/test_medifind.py::test_confirmed_order_deducts_stock_exactly_once -v
```

---

## PostgreSQL Concurrency Test Instructions

These tests require a local PostgreSQL installation and are **separate** from the main pytest suite.

### Setup
```bash
# Install PostgreSQL locally (use version matching your Supabase project where practical)
# Create test database
createdb medifind_test

# Install psycopg2
pip install psycopg2-binary

# Set environment variable (Windows PowerShell)
$env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/medifind_test"

# Apply migrations to test database
$env:DATABASE_URL = $env:TEST_DATABASE_URL
flask db upgrade

# Run concurrency tests
python tests/test_pg_concurrency.py
```

### Safety guarantees
- `TEST_DATABASE_URL` is required (never falls back to `DATABASE_URL`)
- Host must be exactly `localhost` or `127.0.0.1`
- Database name must contain `test`
- Validated using SQLAlchemy's `make_url()`, not raw string matching
- Script cleans up test data automatically

### If PostgreSQL is unavailable
The script exits with a clear SKIPPED message. Tests are never falsely reported as passed.

---

## Vercel Configuration

Vercel deployment configuration is in `vercel.json`. The Flask WSGI app is exposed via `api/index.py`.

### Requirements before deploying
- [ ] `SECRET_KEY` set in Vercel environment variables
- [ ] `DATABASE_URL` set (Supabase transaction pooler URL)
- [ ] `FLASK_ENV=production` set
- [ ] Migrations applied against Supabase PostgreSQL (using direct URL)
- [ ] Private Supabase Storage buckets created
- [ ] `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` set (when Storage is wired)

### Do not deploy until all items above are verified.

---

## Security Considerations

- **Passwords**: Hashed with Werkzeug's `generate_password_hash` (PBKDF2-SHA256).
- **Session cookies**: `HttpOnly`, `SameSite=Lax`. `Secure` flag enforced in production.
- **SECRET_KEY**: Must be set via environment variable in production. No hardcoded fallback.
- **Prices and totals**: Always computed server-side from the inventory record. Browser-submitted prices are never trusted.
- **Inventory**: Never trusted from the browser. Stock check and deduction use row-level locking.
- **Authorization**: Every order, prescription, and inventory endpoint checks role and ownership server-side.
- **Prescription files**: Never served via public URLs. All access requires authentication and permission check.
- **Error messages**: Stack traces and internal details are never exposed to the client.
- **Input validation**: All inputs validated and sanitized server-side.
- **SQL injection**: Prevented by SQLAlchemy's parameterized queries.
- **Idempotency**: Duplicate order submissions detected and short-circuited safely.

---

## Known Limitations & Production Recommendations

1. **CSRF tokens on state-changing API endpoints**: The application uses a JSON API with session cookies protected by `SameSite=Lax` and `HttpOnly`. For high-security production environments, integrating Flask-WTF CSRF tokens on mutating requests is recommended as an additional layer of defense.

2. **Redis distributed rate limiting**: While endpoints validate requests and prevent duplicate orders with unique idempotency keys, an in-memory or Redis-backed rate limiter (e.g., Flask-Limiter) is recommended for production to protect against volumetric brute force.

3. **`datetime.utcnow()` SQLAlchemy schema defaults**: SQLAlchemy's legacy `default=datetime.utcnow` in model column definitions produces deprecation warnings on Python 3.12+. Internal service layers already use timezone-aware UTC. Standardizing the model declarations can be performed in a future migration window.

4. **Vercel deployment verification**: Vercel configuration files (`vercel.json` and `api/index.py`) are fully structured, and the database and file storage run on external cloud services (Supabase PostgreSQL and Supabase Storage). Live deployment to Vercel should be verified on a staging preview before routing production traffic.
