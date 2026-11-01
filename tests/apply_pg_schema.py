"""Apply schema and Alembic version to Supabase PostgreSQL database."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

migration_url = os.getenv('MIGRATION_DATABASE_URL')
if not migration_url:
    print("ERROR: MIGRATION_DATABASE_URL is not set in .env")
    sys.exit(1)

# Set DATABASE_URL to MIGRATION_DATABASE_URL for DDL execution
os.environ['DATABASE_URL'] = migration_url

from backend.app import create_app
from backend.database import db
from backend.config import normalize_database_url
import sqlalchemy as sa

print("Connecting to Supabase PostgreSQL for schema initialization...")
app = create_app()

with app.app_context():
    engine = db.engine
    print(f"Dialect: {engine.dialect.name}")
    
    # 1. Create all tables defined in models.py
    print("Running db.create_all()...")
    db.create_all()
    print("db.create_all() completed.")

    # 2. Check inspector for created tables
    inspector = sa.inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables present in DB: {tables}")

    required_tables = [
        'users', 'pharmacies', 'medicines', 'pharmacy_inventory',
        'prescriptions', 'orders', 'notifications', 'medicine_requests'
    ]
    missing = [t for t in required_tables if t not in tables]
    if missing:
        print(f"ERROR: Missing tables: {missing}")
        sys.exit(2)
    else:
        print("SUCCESS: All 8 MediFind application tables exist!")

    # 3. Ensure alembic_version table is created and stamped to head (9192c7b47ddb)
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """))
        res = conn.execute(sa.text("SELECT version_num FROM alembic_version")).fetchall()
        if not res:
            conn.execute(sa.text("INSERT INTO alembic_version (version_num) VALUES ('9192c7b47ddb')"))
            print("Stamped alembic_version to '9192c7b47ddb' (head).")
        else:
            print(f"alembic_version already set: {[r[0] for r in res]}")

print("PostgreSQL schema initialization verified successfully!")

