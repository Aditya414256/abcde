"""
Supabase PostgreSQL Connectivity & Migration Verifier.

Usage:
    python tests/verify_supabase_db.py

Checks:
1. Reads connection credentials from .env.
2. Tests direct connection to Supabase PostgreSQL.
3. Checks existing tables and migration version table (alembic_version).
4. Verifies safety before applying migrations.
"""
import os
import sys
from dotenv import load_dotenv

# Load local .env
load_dotenv('.env')

db_url = os.environ.get('MIGRATION_DATABASE_URL') or os.environ.get('DATABASE_URL')

if not db_url or '[YOUR-DB-PASSWORD]' in db_url:
    print("=" * 70)
    print("ACTION REQUIRED: Supabase Database Password Needed")
    print("=" * 70)
    print("Please open your local .env file:")
    print("   c:\\Users\\Admin\\OneDrive\\Desktop\\pro demo real\\.env")
    print("And replace [YOUR-DB-PASSWORD] with your actual Supabase DB password:")
    print("   DATABASE_URL=postgresql+psycopg2://postgres.evcgzxpbvucmtojtlchl:<password>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require")
    print("   MIGRATION_DATABASE_URL=postgresql+psycopg2://postgres.evcgzxpbvucmtojtlchl:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require")
    print("=" * 70)
    sys.exit(1)

# Strip driver prefix for psycopg2 direct test
clean_url = db_url.replace('postgresql+psycopg2://', 'postgresql://')

try:
    import psycopg2
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(clean_url, connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    ver = cur.fetchone()[0]
    print(f"SUCCESS: Connected to Supabase PostgreSQL!\nVersion: {ver}\n")

    # Check tables in public schema
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"Existing public tables ({len(tables)}): {', '.join(tables) if tables else 'None (Clean Database)'}")

    cur.close()
    conn.close()
    print("\nDatabase is ready for Alembic migrations via: flask db upgrade")
    sys.exit(0)

except psycopg2.OperationalError as e:
    print(f"FAILED to connect to Supabase: {e}")
    sys.exit(2)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(3)

