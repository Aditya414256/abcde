"""Run the actual Alembic chain on an empty and an adopted database."""
from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy import inspect, text
from backend.database import db
import backend.models


def test_fresh_database_and_repeated_upgrade(tmp_path):
    app=Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI']=f'sqlite:///{tmp_path / "fresh.db"}'
    db.init_app(app);Migrate(app,db)
    with app.app_context():
        assert inspect(db.engine).get_table_names()==[]
        upgrade(directory='migrations')
        upgrade(directory='migrations')
        assert set(db.metadata.tables).issubset(inspect(db.engine).get_table_names())
        for name, table in db.metadata.tables.items():
            assert {c.name for c in table.columns}=={c['name'] for c in inspect(db.engine).get_columns(name)}
        assert db.session.execute(text('select version_num from alembic_version')).scalar()=='9192c7b47ddb'


def test_adopt_existing_schema_preserves_data(tmp_path):
    app=Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI']=f'sqlite:///{tmp_path / "existing.db"}'
    db.init_app(app);Migrate(app,db)
    with app.app_context():
        db.create_all()
        db.session.execute(text("insert into users (id,email,password_hash,full_name,role) values (99,'keep@test','hash','Keep User','customer')"))
        db.session.commit()
        upgrade(directory='migrations')
        assert db.session.execute(text('select full_name from users where id=99')).scalar()=='Keep User'
