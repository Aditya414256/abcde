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
        return jsonify({'status': 'healthy', 'database': 'available'}), 200

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
