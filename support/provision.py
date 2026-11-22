"""Create fictional review accounts once in an explicit local review database."""

import os
import secrets

from sqlalchemy import text

from orderflow.auth import password_record
from orderflow.db import migrate, open_engine

ACCOUNTS = [
    ("customer-a", "alex", "CUSTOMER"),
    ("customer-b", "blair", "CUSTOMER"),
    ("staff-s", "sam", "STAFF"),
]


def main():
    engine = open_engine(os.environ["DATABASE_URL"])
    if engine.url.database != "orderflow_review":
        raise SystemExit("Choose the dedicated orderflow_review database.")
    migrate(engine)
    credentials = []
    with engine.begin() as db:
        for user_id, name, role in ACCOUNTS:
            password = secrets.token_urlsafe(12)
            db.execute(
                text("INSERT INTO users (id,username,role) VALUES (:id,:name,:role)"),
                {"id": user_id, "name": name, "role": role},
            )
            db.execute(
                text("INSERT INTO account_passwords VALUES (:id,:salt,:digest)"),
                {"id": user_id, **password_record(password)},
            )
            credentials.append((name, role, password))
    for name, role, password in credentials:
        print(f"{name} ({role}): {password}")


if __name__ == "__main__":
    main()
