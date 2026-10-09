import os
from flask import Flask, send_from_directory, jsonify
from flask_login import LoginManager
from backend.config import Config, BASE_DIR
from backend.database import db
from backend.models import User

def create_app(config_class=Config):
    frontend_folder = os.path.join(BASE_DIR, 'frontend')
    app = Flask(__name__, static_folder=frontend_folder, static_url_path='')
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        from backend.seed import ensure_schema_migrations
        ensure_schema_migrations()

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from backend.routes.auth_routes import auth_bp
    from backend.routes.medicine_routes import medicine_bp
    from backend.routes.order_routes import order_bp
    from backend.routes.pharmacy_routes import pharmacy_bp
    from backend.routes.admin_routes import admin_bp
    from backend.routes.notification_routes import common_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(medicine_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(pharmacy_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(common_bp)

    # Static frontend page routes
    @app.route('/')
    def index():
        return send_from_directory(frontend_folder, 'HomePage.html')

    @app.route('/<path:filename>')
    def serve_frontend(filename):
        file_path = os.path.join(frontend_folder, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(frontend_folder, filename)
        # Default to index if not found
        return send_from_directory(frontend_folder, 'HomePage.html')

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'Internal server error'}), 500

    return app
