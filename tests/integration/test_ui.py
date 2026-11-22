from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from orderflow.auth import authenticate, password_record
from orderflow.models import Principal

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
    from orderflow import db
    from orderflow.services import OrderService
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
