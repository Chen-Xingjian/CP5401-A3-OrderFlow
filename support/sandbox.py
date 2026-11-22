import os
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from orderflow.db import migrate, open_engine


@contextmanager
def sandbox_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or make_url(url).database != "orderflow_test":
        raise RuntimeError(
            "Set TEST_DATABASE_URL to a dedicated PostgreSQL database named orderflow_test."
        )
    schema = f"test_{uuid4().hex}"
    admin = open_engine(url, poolclass=NullPool)
    engine = open_engine(
        url, poolclass=NullPool, connect_args={"options": f"-c search_path={schema}"}
    )
    with admin.begin() as db:
        db.exec_driver_sql(f"CREATE SCHEMA {schema}")
    try:
        migrate(engine)
        with engine.begin() as db:
            db.exec_driver_sql("""
                INSERT INTO users (id, username, role, active) VALUES
                  ('customer-a', 'alex', 'CUSTOMER', true),
                  ('customer-b', 'blair', 'CUSTOMER', true),
                  ('staff-s', 'sam', 'STAFF', true),
                  ('staff-t', 'taylor', 'STAFF', true),
                  ('inactive', 'inactive', 'STAFF', false)
            """)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
        admin.dispose()
