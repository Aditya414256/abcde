"""Disposable, local-only server for browser regression tests."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['FLASK_ENV'] = 'testing'
from backend.app import create_app
from backend.config import Config
from backend.database import db
from backend.models import Pharmacy

scratch = tempfile.TemporaryDirectory(prefix='medifind-browser-')
Config.UPLOAD_FOLDER = str(Path(scratch.name) / 'prescriptions')
Config.SUPABASE_URL = None
class BrowserConfig:
    TESTING = True
    SECRET_KEY = 'disposable-browser-test-only'
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{scratch.name}/test.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

app = create_app(BrowserConfig)
with app.app_context():
    Pharmacy.query.filter_by(id=1).first().name = "Patil's Pharmacy"
    db.session.commit()
app.run(host='127.0.0.1', port=5056, use_reloader=False)
