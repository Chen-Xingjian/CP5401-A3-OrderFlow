from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from orderflow import db
from orderflow.auth import authenticate, password_record
from orderflow.models import Principal
from orderflow.services import OrderService

APP = Path(__file__).resolve().parents[2] / "src/app.py"
PASSWORD = "fictional-test-password"


@pytest.fixture
def review_shop(database, monkeypatch):
    monkeypatch.setenv("ORDERFLOW_DB_PATH", database.url.database)
    return database


def button(app, label):
    return next(item for item in app.button if item.label == label)


def start():
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    assert not app.exception
    return app


def staff(app):
    app.radio(key="demo_role").set_value("Staff").run()
    assert not app.exception
    return app


def choose(app, user_id):
    app.selectbox(key="demo_user").set_value(user_id).run()
    assert not app.exception


def test_t20_customer_order_and_shared_browser_switch(review_shop):
    app = start()
    assert app.selectbox(key="demo_user").options == ["Alex", "Blair"]
    assert not app.text_input
    app.number_input(key="copies_customer-a").set_value(2)
    app.text_area(key="note_customer-a").set_value("Collect on Friday")
    button(app, "Place order").click().run()
    assert app.success[0].value == "Order placed."
    assert app.text[0].value == "Collect on Friday"
    assert all(item.label != "Confirm order" for item in app.button)
    app.text_area(key="note_customer-a").set_value("Alex draft")
    choose(app, "customer-b")
    assert not app.text and not app.success
    assert app.text_area(key="note_customer-b").value == ""
    assert app.number_input(key="copies_customer-b").value == 1
    assert app.info[0].value.startswith("Your orders will appear here")
    choose(app, "customer-a")
    assert app.text[0].value == "Collect on Friday"


def test_t20_two_staff_sessions_and_handover(review_shop, service):
    customer = Principal("customer-a")
    order = service.create_order(customer, service_id="bw-print", quantity=2)
    first, second = staff(start()), staff(start())
    assert first.selectbox(key="demo_user").options == ["Sam", "Taylor"]
    assert not first.text_area
    choose(second, "staff-t")
    button(first, "Confirm order").click().run()
    button(second, "Confirm order").click().run()
    assert "Refresh" in second.error[0].value
    assert service.get_order(customer, order.id).order.version == 1
    for label in ["Start production", "Mark ready for pickup"]:
        button(first, label).click().run()
    first.radio(key="demo_role").set_value("Customer").run()
    assert first.subheader[0].value == "Ready for pickup"
    assert any("Collect them" in m.value for m in first.markdown)
    assert all(item.label != "Confirm handover" for item in first.button)
    staff(first)
    choose(first, "staff-t")
    button(first, "Confirm handover").click().run()
    assert not first.exception
    assert all(item.label != "Confirm handover" for item in first.button)
    first.radio(key="demo_role").set_value("Customer").run()
    assert first.subheader[0].value == "Completed"
    history = service.get_order(customer, order.id).history
    assert [event.actor_id for event in history] == [
        "customer-a",
        "staff-s",
        "staff-s",
        "staff-s",
        "staff-t",
    ]


def test_t20_inactive_and_non_demo_users(review_shop):
    app = staff(start())
    with review_shop.begin() as db:
        db.exec_driver_sql("UPDATE users SET active=false WHERE id='staff-s'")
        db.exec_driver_sql(
            "INSERT INTO users (id, username, role) VALUES ('other','other','STAFF')"
        )
    button(app, "Refresh orders").click().run()
    assert not app.exception
    assert app.selectbox(key="demo_user").options == ["Taylor"]
    with review_shop.begin() as db:
        db.execute(text("UPDATE users SET active=false WHERE id='staff-t'"))
    button(app, "Refresh orders").click().run()
    assert not app.selectbox
    assert app.info[0].value == "No active demo users are available for this role."


def test_demo_preparation_preserves_existing_orders_and_inactive_accounts(review_shop, service):
    from orderflow import demo

    owner = Principal("customer-a")
    order = service.create_order(owner, service_id="bw-print", quantity=1)
    snapshot = service.get_order(owner, order.id)
    with review_shop.begin() as db:
        db.exec_driver_sql("DELETE FROM users WHERE id='staff-t'")
        db.exec_driver_sql("UPDATE users SET active=false WHERE id='customer-b'")
    demo.prepare(review_shop)
    demo.prepare(review_shop)
    assert demo.choices(review_shop, "STAFF") == {"staff-s": "Sam", "staff-t": "Taylor"}
    assert demo.choices(review_shop, "CUSTOMER") == {"customer-a": "Alex"}
    assert service.get_order(owner, order.id) == snapshot


def test_sqlite_migration_preserves_existing_history(tmp_path, monkeypatch):
    from support.sandbox import sandbox_database

    migrations = db.MIGRATIONS
    baseline = migrations / "001_baseline.sql"
    (tmp_path / baseline.name).write_bytes(baseline.read_bytes())
    with monkeypatch.context() as patch:
        patch.setattr(db, "MIGRATIONS", tmp_path)
        with sandbox_database() as legacy:
            svc = OrderService(legacy)
            owner = Principal("customer-a")
            order = svc.create_order(owner, service_id="bw-print", quantity=2)
            svc.advance_order(
                Principal("staff-s"), order.id, target="CONFIRMED", expected_version=0
            )
            snapshot = svc.get_order(owner, order.id)
            patch.setattr(db, "MIGRATIONS", migrations)
            db.migrate(legacy)
            with legacy.begin() as connection:
                connection.execute(
                    text("INSERT INTO account_passwords VALUES ('customer-a',:salt,:digest)"),
                    password_record(PASSWORD),
                )
            assert svc.get_order(authenticate(legacy, "alex", PASSWORD), order.id) == snapshot


def test_t28_confirmed_cancellation_and_staff_queue(review_shop, service):
    order = service.create_order(Principal("customer-a"), service_id="bw-print", quantity=2)
    app = start()
    assert button(app, "Cancel order")
    choose(app, "customer-b")
    assert not any(b.label == "Cancel order" for b in app.button)
    staff(app)
    assert not any(b.label == "Cancel order" for b in app.button)
    button(app, "Confirm order").click().run()
    app.radio(key="demo_role").set_value("Customer").run()
    button(app, "Cancel order").click().run()
    assert not app.exception and app.success[0].value == "Order cancelled."
    assert app.subheader[0].value == "Cancelled"
    assert any(m.value == "Confirmed → Cancelled" for m in app.markdown)
    staff(app)
    assert app.selectbox(key="chosen").value == str(order.id)
    assert app.subheader[0].value == "Cancelled"
    assert not any(b.key and b.key.startswith(("advance_", "cancel_")) for b in app.button)


def test_t28_stale_owner_page_requests_refresh(review_shop, service):
    owner = Principal("customer-a")
    order = service.create_order(owner, service_id="bw-print", quantity=2)
    sam = Principal("staff-s")
    service.advance_order(sam, order.id, target="CONFIRMED", expected_version=0)
    app = start()
    service.advance_order(sam, order.id, target="PROCESSING", expected_version=1)
    button(app, "Cancel order").click().run()
    assert not app.exception and not app.success
    assert "Refresh" in app.error[0].value
    assert app.subheader[0].value == "In production"
    assert not any(b.label == "Cancel order" for b in app.button)
    assert len(service.get_order(owner, order.id).history) == 3


def test_t27_warm_upgrade_cancels_on_first_attempt(tmp_path, monkeypatch, v10_migrations):
    path = tmp_path / "live.sqlite3"
    monkeypatch.setenv("ORDERFLOW_DB_PATH", str(path))
    # Keep the same entry point, database path, Streamlit session and resource cache.
    with monkeypatch.context() as old:
        old.setattr(db, "MIGRATIONS", v10_migrations)
        app = start()
        button(app, "Place order").click().run()
        assert app.success[0].value == "Order placed."
    engine = db.open_engine(path)
    try:
        owner = Principal("customer-a")
        service = OrderService(engine)
        (order,) = service.list_orders(owner)
        before = service.get_order(owner, order.id)
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT count(*) FROM schema_migrations").scalar_one() == 2
        app.run()
        button(app, "Cancel order").click().run()
        assert [message.value for message in app.success] == ["Order cancelled."]
        after = service.get_order(owner, order.id)
        assert after.history[:-1] == before.history
        assert (after.order.status, after.order.version, after.history[-1].actor_id) == (
            "CANCELLED",
            order.version + 1,
            "customer-a",
        )
        with engine.connect() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM schema_migrations WHERE name='003_customer_cancellation.sql'"
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()


def test_t30_staff_workload_and_handover(review_shop, service, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from orderflow import repository

    def totals(app):
        return {
            b.label.rsplit(" (", 1)[0]: int(b.label.rsplit("(", 1)[1][:-1])
            for b in app.button
            if b.key and b.key.startswith("filter_")
        }

    sam = Principal("staff-s")
    alex = Principal("customer-a")
    blair = Principal("customer-b")
    app = staff(start())
    empty = {"Pending confirmation": 0, "Confirmed": 0, "In production": 0, "Ready for pickup": 0}
    empty.update({"Completed": 0, "Cancelled": 0, "Pickup overdue": 0})
    assert totals(app) == empty

    class OldClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(UTC) - timedelta(hours=49)

    with monkeypatch.context() as old:
        old.setattr(repository, "datetime", OldClock)
        ready = service.create_order(blair, service_id="bw-print", quantity=1)
        for stage in ("CONFIRMED", "PROCESSING", "READY_FOR_PICKUP"):
            ready = service.advance_order(
                sam, ready.id, target=stage, expected_version=ready.version
            )
    fresh = service.create_order(alex, service_id="bw-print", quantity=1)
    for stage in ("CONFIRMED", "PROCESSING", "READY_FOR_PICKUP"):
        fresh = service.advance_order(sam, fresh.id, target=stage, expected_version=fresh.version)
    pending = service.create_order(alex, service_id="bw-print", quantity=3)
    confirmed = service.create_order(blair, service_id="bw-print", quantity=1)
    service.advance_order(sam, confirmed.id, target="CONFIRMED", expected_version=0)
    processing = service.create_order(alex, service_id="bw-print", quantity=1)
    service.advance_order(sam, processing.id, target="CONFIRMED", expected_version=0)
    service.advance_order(sam, processing.id, target="PROCESSING", expected_version=1)
    cancelled = service.create_order(blair, service_id="bw-print", quantity=1)
    service.cancel_order(blair, cancelled.id, expected_version=0)
    active = {
        **empty,
        "Pending confirmation": 1,
        "Confirmed": 1,
        "In production": 1,
        "Cancelled": 1,
    }
    button(app, "Refresh orders").click().run()
    assert totals(app) == {**active, "Ready for pickup": 2, "Pickup overdue": 1}
    assert any("1 of 2" in c.value for c in app.caption)
    picker = app.selectbox(key="chosen")
    assert sum("Pickup overdue" in option for option in picker.options) == 1
    full_counts = totals(app)
    members = {
        "PENDING": [pending],
        "CONFIRMED": [confirmed],
        "PROCESSING": [processing],
        "READY_FOR_PICKUP": [ready, fresh],
        "CANCELLED": [cancelled],
        "OVERDUE": [ready],
    }
    for stage, expected in members.items():
        app.button(key=f"filter_{stage}").click().run()
        assert not app.exception
        options = app.selectbox(key="chosen").options
        assert {option.split(" · ")[0] for option in options} == {
            str(order.id)[:8].upper() for order in expected
        }
        assert app.selectbox(key="chosen").value in {str(order.id) for order in expected}
        assert totals(app) == full_counts

    button(app, "Refresh orders").click().run()
    assert app.selectbox(key="chosen").value == str(ready.id)
    assert "Ready since" in app.warning[0].value
    button(app, "Confirm handover").click().run()
    assert not app.warning
    assert any("No orders match the Pickup overdue filter" in item.value for item in app.info)
    assert not any(s.key == "chosen" for s in app.selectbox) and not app.subheader
    button(app, "Clear filter").click().run()
    assert len(app.selectbox(key="chosen").options) == 6
    assert button(app, "Clear filter").disabled
    app.button(key="filter_COMPLETED").click().run()
    assert app.selectbox(key="chosen").value == str(ready.id)
    assert totals(app) == {**active, "Ready for pickup": 1, "Completed": 1}
    assert any("0 of 1" in c.value for c in app.caption)
    history = service.get_order(blair, ready.id).history
    assert len(history) == 5 and history[-1].to_status == "COMPLETED"

    app.radio(key="demo_role").set_value("Customer").run()
    assert not totals(app) and not app.warning
    assert all("Pickup overdue" not in c.value for c in app.caption)


def test_t31_staff_filter_resets_on_identity_change(review_shop, service):
    order = service.create_order(Principal("customer-a"), service_id="bw-print", quantity=1)
    app = staff(start())
    app.button(key="filter_CANCELLED").click().run()
    assert not any(s.key == "chosen" for s in app.selectbox)
    choose(app, "staff-t")
    assert button(app, "Clear filter").disabled
    assert app.selectbox(key="chosen").value == str(order.id)
    app.button(key="filter_CONFIRMED").click().run()
    app.radio(key="demo_role").set_value("Customer").run()
    assert app.selectbox(key="chosen").value == str(order.id)
    assert all(b.label != "Clear filter" for b in app.button)
