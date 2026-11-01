"""
Vercel serverless entry point for MediFind Flask application.

IMPORTANT NOTES FOR VERCEL DEPLOYMENT:
1. The local filesystem is ephemeral on Vercel. Do not write prescription files
   to disk in production. Use Supabase Storage instead.
2. Database connections: use the Supabase transaction pooler URL (port 6543),
   not the direct database URL. The direct URL is for migrations only.
3. Run migrations manually with: flask db upgrade --database <MIGRATION_DATABASE_URL>
4. Set all environment variables in the Vercel project settings, not in code.
5. The 4.5 MB Vercel request body limit means prescription uploads must go
   directly to Supabase Storage via signed upload URLs, not through this function.

Required environment variables in Vercel:
  SECRET_KEY
  DATABASE_URL           (Supabase transaction pooler URL)
  FLASK_ENV=production
  SUPABASE_URL           (when Supabase Storage is configured)
  SUPABASE_SERVICE_ROLE_KEY (when Supabase Storage is configured)
"""
import sys
import os

# Ensure the project root is on the Python path so backend imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.config import ProductionConfig

# The Flask application instance exposed to the Vercel Python runtime
app = create_app(ProductionConfig)

# Vercel looks for `app` (a WSGI callable) in this module

