"""
Vercel serverless entry point for MediFind Flask application.
"""
import sys
import os
import logging

# Ensure the project root is on the Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

app = None
init_error = None

try:
    from backend.app import create_app
    from backend.config import Config
    from backend.database import db
    from backend.models import User

    app = create_app(Config)

    # Add quick health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        from flask import jsonify
        db_status = 'unknown'
        try:
            db_status = db.engine.dialect.name
            User.query.limit(1).all()
        except Exception:
            app.logger.exception('Database health check failed')
            return jsonify({'status': 'unhealthy', 'database': 'unavailable'}), 503
        return jsonify({'status': 'healthy', 'database': 'available',
                        'version': os.environ.get('VERCEL_GIT_COMMIT_SHA', 'local')}), 200

    @app.route('/api/health/storage', methods=['GET'])
    def storage_health_check():
        """Read-only check of private Supabase bucket access (no files changed)."""
        from flask import jsonify
        import urllib.request
        from backend.services.supabase_storage_service import SupabaseStorageService
        if not SupabaseStorageService.is_configured():
            return jsonify({'status': 'unhealthy', 'storage': 'unavailable'}), 503
        try:
            base = SupabaseStorageService.get_base_url()
            headers = SupabaseStorageService._get_headers()
            for bucket in (app.config['SUPABASE_PRESCRIPTIONS_BUCKET'], app.config['SUPABASE_PHARMACY_DOCS_BUCKET']):
                req = urllib.request.Request(
                    f'{base}/storage/v1/bucket/{bucket}', headers=headers, method='GET'
                )
                with urllib.request.urlopen(req, timeout=8) as response:
                    if response.status != 200:
                        raise RuntimeError('Private storage bucket access failed')
        except Exception:
            app.logger.exception('Supabase private bucket check failed')
            return jsonify({'status': 'unhealthy', 'storage': 'unavailable'}), 503
        return jsonify({'status': 'healthy', 'storage': 'available'}), 200

except Exception as err:
    logging.exception('MediFind app initialization failed')

if app is None:
    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    @app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def initialization_failure(path):
        return jsonify({
            'error': 'Application initialization failed'
        }), 500
