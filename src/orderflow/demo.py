"""The four fictional identities available in the public teaching demo."""

from sqlalchemy import text

from .db import migrate, transaction

PEOPLE = (
    ("customer-a", "alex", "CUSTOMER"),
    ("customer-b", "blair", "CUSTOMER"),
    ("staff-s", "sam", "STAFF"),
    ("staff-t", "taylor", "STAFF"),
)


def prepare(engine):
    migrate(engine)
    with transaction(engine, write=True) as db:
        db.execute(
            text("""INSERT INTO users (id,username,role) VALUES (:id,:name,:role)
                    ON CONFLICT DO NOTHING"""),
            [{"id": uid, "name": name, "role": role} for uid, name, role in PEOPLE],
        )


def choices(engine, role):
    with transaction(engine) as db:
        active = db.execute(
            text("SELECT id,username FROM users WHERE role=:role AND active"),
            {"role": role},
        )
        names = dict(active.tuples().all())
    return {
        uid: name.title() for uid, name, group in PEOPLE if group == role and names.get(uid) == name
    }
