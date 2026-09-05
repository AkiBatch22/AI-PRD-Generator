import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema
from app.db import Base, get_db, settings
from app.main import app
from app.seed import seed


@pytest.fixture
def db():
    url = os.environ.get('TEST_DATABASE_URL')
    schema = None
    if url:
        engine = create_engine(url)
        if engine.dialect.name != 'postgresql':
            raise ValueError('TEST_DATABASE_URL must use PostgreSQL; omit it for SQLite')
        # Each test owns only this temporary schema, never the database's public tables.
        schema = 'test_' + uuid4().hex
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        test_engine = engine.execution_options(schema_translate_map={None: schema})
    else:
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        @event.listens_for(engine, 'connect')
        def enable_fk(conn, _):
            conn.execute('PRAGMA foreign_keys=ON')
        test_engine = engine
    try:
        Base.metadata.create_all(test_engine)
        factory = sessionmaker(test_engine, expire_on_commit=False)
        with factory() as session:
            seed(session)
            yield session
    finally:
        if schema:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(settings, 'llm_provider', 'mock')
    def override():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
    app.dependency_overrides[get_db] = override
    client = TestClient(app, raise_server_exceptions=True)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()
