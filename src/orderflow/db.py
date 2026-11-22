"""Connect to PostgreSQL and apply the baseline as an explicit deployment step."""

import hashlib
import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from .models import OrderError

MIGRATION = Path(__file__).resolve().parents[2] / "db/migrations/001_baseline.sql"


def open_engine(url: str, **options) -> Engine:
    parsed = make_url(url)
    if parsed.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("OrderFlow requires PostgreSQL with the psycopg driver.")
    return create_engine(
        parsed.set(drivername="postgresql+psycopg"),
        isolation_level="READ COMMITTED",
        hide_parameters=True,
        **options,
    )


@contextmanager
def transaction(engine: Engine):
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
            yield connection
    except SQLAlchemyError:
        raise OrderError(
            "PERSISTENCE_ERROR",
            "The operation could not be confirmed. Refresh and check the order.",
        ) from None


def migrate(engine: Engine) -> None:
    sql = MIGRATION.read_bytes()
    digest = hashlib.sha256(sql).hexdigest()
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(5401, 1)"))
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name text PRIMARY KEY, sha256 text NOT NULL)"
        )
        applied = connection.execute(
            text("SELECT sha256 FROM schema_migrations WHERE name = :name"),
            {"name": MIGRATION.name},
        ).scalar_one_or_none()
        if applied is None:
            connection.exec_driver_sql(sql.decode("utf-8"))
            connection.execute(
                text("INSERT INTO schema_migrations VALUES (:name, :digest)"),
                {"name": MIGRATION.name, "digest": digest},
            )
        elif applied != digest:
            raise RuntimeError("The installed baseline differs from the migration file.")


if __name__ == "__main__":
    engine = open_engine(os.environ["DATABASE_URL"])
    try:
        migrate(engine)
        print("OrderFlow baseline is ready.")
    finally:
        engine.dispose()
