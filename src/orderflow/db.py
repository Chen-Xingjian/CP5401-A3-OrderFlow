"""Open the local SQLite file and apply migrations atomically."""

import hashlib
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from .models import OrderError

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "db/migrations"


def database_path() -> Path:
    configured = os.getenv("ORDERFLOW_DB_PATH")
    return (
        Path(configured).expanduser().resolve()
        if configured
        else ROOT / ".local-review/orderflow.sqlite3"
    )


def open_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(path)), connect_args={"timeout": 10})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys = ON")

    @event.listens_for(engine, "begin")
    def begin(connection):
        # Reserve the single writer before reading the version or checking the actor.
        sql = "BEGIN IMMEDIATE" if connection.get_execution_options().get("write") else "BEGIN"
        connection.exec_driver_sql(sql)

    return engine


@contextmanager
def transaction(engine: Engine, *, write=False):
    try:
        with engine.execution_options(write=write).begin() as db:
            yield db
    except SQLAlchemyError:
        raise OrderError(
            "PERSISTENCE_ERROR",
            "The operation could not be confirmed. Refresh and check the order.",
        ) from None


def migrate(engine: Engine) -> None:
    with engine.execution_options(write=True).begin() as db:
        db.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name TEXT PRIMARY KEY, sha256 TEXT NOT NULL)"
        )
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            sql = migration.read_bytes()
            digest = hashlib.sha256(sql).hexdigest()
            applied = db.execute(
                text("SELECT sha256 FROM schema_migrations WHERE name = :name"),
                {"name": migration.name},
            ).scalar_one_or_none()
            if applied is not None:
                if applied != digest:
                    raise RuntimeError("An installed migration differs from its source file.")
                continue
            # executescript can implicitly commit. Execute complete statements inside our transaction.
            statement = ""
            for line in sql.decode().splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    db.exec_driver_sql(statement)
                    statement = ""
            if statement.strip():
                raise RuntimeError("Incomplete migration statement.")
            db.execute(
                text("INSERT INTO schema_migrations VALUES (:name, :digest)"),
                {"name": migration.name, "digest": digest},
            )


if __name__ == "__main__":
    engine = open_engine(database_path())
    try:
        migrate(engine)
        print("OrderFlow baseline is ready.")
    finally:
        engine.dispose()
