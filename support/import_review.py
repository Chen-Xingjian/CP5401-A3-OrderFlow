"""Copy an existing local PostgreSQL demo shop to a new SQLite file."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from orderflow.db import database_path, migrate, open_engine

TABLES = {
    "users": ("id", "username", "role", "active"),
    "service_catalogue": ("id", "name", "active"),
    "orders": (
        "id",
        "owner_id",
        "service_id",
        "service_name_snapshot",
        "quantity",
        "note",
        "status",
        "version",
        "created_at",
        "updated_at",
    ),
    "order_history": (
        "order_id",
        "sequence",
        "from_status",
        "to_status",
        "actor_id",
        "occurred_at",
    ),
}


def read_shop(socket: Path):
    # One SELECT takes one consistent snapshot of all four source tables.
    fields = [
        f"'{table}', (SELECT COALESCE(json_agg(row_to_json(r)), '[]'::json) "
        f"FROM (SELECT {', '.join(columns)} FROM {table}) r)"
        for table, columns in TABLES.items()
    ]
    result = subprocess.run(
        [
            "psql",
            "-XqAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            str(socket),
            "-U",
            "orderflow",
            "-d",
            "orderflow_review",
            "-c",
            f"SELECT json_build_object({', '.join(fields)})",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def import_snapshot(snapshot, target: Path):
    if target.exists():
        raise FileExistsError(f"SQLite file already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent) as directory:
        staged = Path(directory) / "shop.sqlite3"
        staged.touch(mode=0o600)
        engine = open_engine(staged)
        try:
            migrate(engine)
            with engine.begin() as db:
                # Replace only the default catalogue in the empty staging database.
                db.exec_driver_sql("DELETE FROM service_catalogue")
                for table, columns in TABLES.items():
                    rows = []
                    for item in snapshot[table]:
                        values = []
                        for column in columns:
                            value = item[column]
                            if column in ("created_at", "updated_at", "occurred_at"):
                                value = (
                                    datetime.fromisoformat(value)
                                    .astimezone(UTC)
                                    .isoformat(timespec="microseconds")
                                )
                            values.append(value)
                        rows.append(tuple(values))
                    if rows:
                        markers = ", ".join("?" for _ in columns)
                        db.exec_driver_sql(
                            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({markers})", rows
                        )
                    actual = db.exec_driver_sql(f"SELECT {', '.join(columns)} FROM {table}").all()
                    if set(actual) != set(rows) or len(actual) != len(rows):
                        raise ValueError(f"Copy verification failed for {table}")
                if db.exec_driver_sql("PRAGMA foreign_key_check").first():
                    raise ValueError("Foreign-key check failed")
        finally:
            engine.dispose()
        # Atomic publication. A concurrent importer cannot replace an existing file.
        os.link(staged, target)


def main():
    target = database_path()
    snapshot = read_shop(Path(__file__).resolve().parents[1] / ".local-review")
    import_snapshot(snapshot, target)
    print(f"Verified {len(snapshot['orders'])} orders and {len(snapshot['order_history'])} events.")


if __name__ == "__main__":
    main()
