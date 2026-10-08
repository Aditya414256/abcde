import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'medifind-super-secret-key-2026-safe')
    
    # SQLite fallback, or MySQL if DATABASE_URL is configured
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f"sqlite:///{os.path.join(BASE_DIR, 'medifind.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder for prescriptions (protected, not served directly without auth)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'prescriptions')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}
