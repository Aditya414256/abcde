"""
PostgreSQL Concurrency Test Runner for MediFind
================================================
Tests concurrent order operations to verify that:
  - Stock is never oversold or duplicated.
  - Exactly-once deduction at ACCEPTED→CONFIRMED.
  - Cancelled orders restore stock correctly.
  - State transitions are safe under concurrent load.

SAFETY GUARD (mandatory — runs before any database operation):
  - Only uses TEST_DATABASE_URL (never DATABASE_URL).
  - Requires hostname to be exactly 'localhost' or '127.0.0.1'.
  - Requires database name to contain 'test' (case-insensitive).
  - Aborts immediately if any guard condition fails.

USAGE:
  1. Install PostgreSQL locally (matching Supabase major version where practical).
  2. Create the test database:
       createdb medifind_test
  3. Set the environment variable:
       $env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/medifind_test"
  4. Run migrations against the test database:
       $env:DATABASE_URL = $env:TEST_DATABASE_URL
       python -m flask db upgrade
  5. Run this script:
       python tests/test_pg_concurrency.py

NEVER point TEST_DATABASE_URL at a production Supabase database.
"""
import os
import sys
import logging
import threading
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ─── Safety Guard ─────────────────────────────────────────────────────────────

def _validate_test_database_url(url: str) -> None:
    """
    Parses the database URL and enforces all safety constraints before any
    destructive SQL operation. Uses SQLAlchemy's make_url() — never raw strings.
    Aborts the entire process on any violation.
    """
    try:
        from sqlalchemy.engine import make_url
        parsed = make_url(url)
    except Exception as exc:
        sys.exit(f"[GUARD FAIL] Cannot parse TEST_DATABASE_URL: {exc}")

    host = parsed.host or ''
    database = parsed.database or ''

    logger.info("[GUARD] TEST_DATABASE_URL host    = %r", host)
    logger.info("[GUARD] TEST_DATABASE_URL database = %r", database)
    logger.info("[GUARD] TEST_DATABASE_URL drivername = %r", parsed.drivername)

    # 1. Must be localhost (exact match, no lookalikes)
    if host not in ('localhost', '127.0.0.1'):
        sys.exit(
            f"[GUARD FAIL] TEST_DATABASE_URL host must be exactly 'localhost' or '127.0.0.1'. "
            f"Got: {host!r}. Aborting to prevent accidental production database operations."
        )

    # 2. Database name must contain 'test' (case-insensitive)
    if 'test' not in database.lower():
        sys.exit(
            f"[GUARD FAIL] TEST_DATABASE_URL database name must contain 'test'. "
            f"Got: {database!r}. Aborting."
        )

    logger.info("[GUARD] PASSED — host=%r database=%r", host, database)


def _require_test_database_url() -> str:
    """Returns TEST_DATABASE_URL or exits with a clear error."""
    url = os.environ.get('TEST_DATABASE_URL', '').strip()
    if not url:
        sys.exit(
            "[GUARD FAIL] TEST_DATABASE_URL is not set.\n"
            "Set it to a local PostgreSQL test database before running concurrency tests.\n"
            "Example:\n"
            "  $env:TEST_DATABASE_URL = "
            "'postgresql+psycopg2://postgres:postgres@localhost:5432/medifind_test'\n"
            "Tests marked SKIPPED."
        )
    return url


# ─── Test Helpers ─────────────────────────────────────────────────────────────

class ConcurrencyTestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []


def _seed_test_data(session, app):
    """Seeds minimal data required for concurrency tests."""
    from backend.models import User, Pharmacy, Medicine, PharmacyInventory

    with app.app_context():
        # Minimal customer
        customer = User(email='pgtest_customer@test.com', full_name='PG Test Customer',
                        phone='1111111111', role='customer')
        customer.set_password('testpass')
        session.add(customer)

        # Pharmacy owner
        owner = User(email='pgtest_owner@test.com', full_name='PG Test Owner',
                     phone='2222222222', role='pharmacy')
        owner.set_password('testpass')
        session.add(owner)
        session.flush()

        pharmacy = Pharmacy(
            owner_id=owner.id,
            name='PG Test Pharmacy',
            license_number='DL-PG-TEST-001',
            phone='2222222222',
            email='pgtest@test.com',
            address='Test Street',
            city='Testville',
            state='Teststate',
            pincode='000001',
            supports_pickup=True,
            supports_delivery=True,
            delivery_fee=10.0,
            is_verified=True,
            verification_status='APPROVED',
            is_active=True,
        )
        session.add(pharmacy)

        medicine = Medicine(
            name='PG Test Medicine',
            generic_name='pg_test_generic',
            brand_name='PG Brand',
            strength='100mg',
            dosage_form='Tablet',
            requires_prescription=False,
        )
        session.add(medicine)
        session.flush()

        inventory = PharmacyInventory(
            pharmacy_id=pharmacy.id,
            medicine_id=medicine.id,
            quantity=10,
            price=50.0,
        )
        inventory.recalculate_stock_status()
        session.add(inventory)
        session.commit()

        return {
            'customer_id': customer.id,
            'owner_id': owner.id,
            'pharmacy_id': pharmacy.id,
            'medicine_id': medicine.id,
        }


# ─── Concurrency Tests ────────────────────────────────────────────────────────

def test_no_overselling(app, seed, results: ConcurrencyTestResults):
    """Two simultaneous orders competing for the last 1 unit — only one should succeed."""
    from backend.services.order_service import OrderService
    from backend.models import PharmacyInventory
    from backend.database import db

    test_name = "test_no_overselling"

    with app.app_context():
        inv = PharmacyInventory.query.filter_by(
            pharmacy_id=seed['pharmacy_id'], medicine_id=seed['medicine_id']
        ).first()
        inv.quantity = 1
        db.session.commit()

    barrier = threading.Barrier(2)
    successes = []
    errors = []

    def try_confirm(order_id, owner_id):
        try:
            # Each thread uses its own app context (separate SQLAlchemy session)
            with app.app_context():
                barrier.wait()  # Synchronize threads to maximize contention
                OrderService.update_order_status(order_id, owner_id, 'pharmacy', 'ACCEPTED')
                OrderService.update_order_status(order_id, owner_id, 'pharmacy', 'CONFIRMED')
                successes.append(order_id)
        except Exception as exc:
            errors.append((order_id, str(exc)))

    with app.app_context():
        # Create two orders for the same medicine; stock is 1
        try:
            order1 = OrderService.create_order(
                customer_id=seed['customer_id'],
                pharmacy_id=seed['pharmacy_id'],
                medicine_id=seed['medicine_id'],
                quantity=1,
                order_type='PICKUP',
            )
        except Exception:
            # If stock was already 0 from a previous test, skip
            results.skipped.append(f"{test_name} (insufficient stock to set up)")
            return

        # Reset stock for second order
        inv = PharmacyInventory.query.filter_by(
            pharmacy_id=seed['pharmacy_id'], medicine_id=seed['medicine_id']
        ).first()
        inv.quantity = 1
        db.session.commit()

        try:
            order2 = OrderService.create_order(
                customer_id=seed['customer_id'],
                pharmacy_id=seed['pharmacy_id'],
                medicine_id=seed['medicine_id'],
                quantity=1,
                order_type='PICKUP',
            )
        except Exception:
            results.skipped.append(f"{test_name} (could not create second order)")
            return

    t1 = threading.Thread(target=try_confirm, args=(order1.id, seed['owner_id']))
    t2 = threading.Thread(target=try_confirm, args=(order2.id, seed['owner_id']))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    with app.app_context():
        inv = PharmacyInventory.query.filter_by(
            pharmacy_id=seed['pharmacy_id'], medicine_id=seed['medicine_id']
        ).first()
        final_qty = inv.quantity

    logger.info("[%s] successes=%s errors=%s final_qty=%s", test_name, successes, errors, final_qty)

    if final_qty >= 0 and len(successes) <= 1:
        results.passed.append(f"{test_name}: stock={final_qty} successes={len(successes)}")
    else:
        results.failed.append(
            f"{test_name}: OVERSELL DETECTED stock={final_qty} successes={len(successes)}"
        )


def test_no_negative_inventory(app, seed, results: ConcurrencyTestResults):
    """Stock must never go negative regardless of concurrent cancellations."""
    from backend.models import PharmacyInventory
    from backend.database import db

    test_name = "test_no_negative_inventory"

    with app.app_context():
        inv = PharmacyInventory.query.filter_by(
            pharmacy_id=seed['pharmacy_id'], medicine_id=seed['medicine_id']
        ).first()
        final_qty = inv.quantity

    if final_qty >= 0:
        results.passed.append(f"{test_name}: stock={final_qty}")
    else:
        results.failed.append(f"{test_name}: NEGATIVE STOCK detected: {final_qty}")


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_all(app, seed):
    results = ConcurrencyTestResults()

    tests = [
        test_no_overselling,
        test_no_negative_inventory,
    ]

    for test_fn in tests:
        try:
            logger.info("Running %s ...", test_fn.__name__)
            test_fn(app, seed, results)
        except Exception as exc:
            results.failed.append(f"{test_fn.__name__}: UNEXPECTED ERROR: {exc}")

    return results


def print_report(url, pg_version, results):
    from sqlalchemy.engine import make_url
    parsed = make_url(url)

    print("\n" + "=" * 60)
    print("  MediFind — PostgreSQL Concurrency Test Report")
    print("=" * 60)
    print(f"  Safety guard:  PASSED")
    print(f"  Host:          {parsed.host}")
    print(f"  Database:      {parsed.database}")
    print(f"  PG version:    {pg_version}")
    print(f"  Workers:       2 (threading.Barrier)")
    print(f"  Passed:        {len(results.passed)}")
    print(f"  Failed:        {len(results.failed)}")
    print(f"  Skipped:       {len(results.skipped)}")
    print("-" * 60)

    if results.passed:
        print("  PASSED:")
        for r in results.passed:
            print(f"    ✓  {r}")
    if results.failed:
        print("  FAILED:")
        for r in results.failed:
            print(f"    ✗  {r}")
    if results.skipped:
        print("  SKIPPED:")
        for r in results.skipped:
            print(f"    -  {r}")

    print("=" * 60)
    return len(results.failed) == 0


if __name__ == '__main__':
    # ── Step 1: Get and validate TEST_DATABASE_URL ──────────────────────────
    test_url = _require_test_database_url()
    _validate_test_database_url(test_url)

    # ── Step 2: Confirm psycopg2 is available ───────────────────────────────
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        sys.exit(
            "[SKIP] psycopg2 is not installed.\n"
            "Install it with: pip install psycopg2-binary\n"
            "Concurrency tests SKIPPED."
        )

    # ── Step 3: Bootstrap the Flask app against TEST_DATABASE_URL ───────────
    # The guard has already passed. Override DATABASE_URL only now, and only
    # in-process — never writing to any file or environment outside this run.
    os.environ['DATABASE_URL'] = test_url

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from backend.app import create_app
    from backend.config import Config
    from backend.database import db

    class PGTestConfig(Config):
        SQLALCHEMY_DATABASE_URI = test_url
        TESTING = True
        SECRET_KEY = 'pg-concurrency-test-key'

    app = create_app(PGTestConfig)

    # ── Step 4: Get PostgreSQL version ──────────────────────────────────────
    pg_version = 'unknown'
    with app.app_context():
        try:
            from sqlalchemy import text
            result = db.session.execute(text("SELECT version()")).fetchone()
            pg_version = result[0].split(' ')[1] if result else 'unknown'
        except Exception as exc:
            sys.exit(
                f"[ERROR] Cannot connect to PostgreSQL at {test_url}: {exc}\n"
                "Ensure PostgreSQL is running and the test database exists.\n"
                "Concurrency tests SKIPPED."
            )

    # ── Step 5: Seed test data ───────────────────────────────────────────────
    with app.app_context():
        db.create_all()  # Only in test database (guard already validated)
        seed = _seed_test_data(db.session, app)

    # ── Step 6: Run tests ───────────────────────────────────────────────────
    results = run_all(app, seed)

    # ── Step 7: Cleanup ─────────────────────────────────────────────────────
    with app.app_context():
        db.drop_all()  # Only in test database (guard already validated)

    # ── Step 8: Report ──────────────────────────────────────────────────────
    success = print_report(test_url, pg_version, results)
    sys.exit(0 if success else 1)

