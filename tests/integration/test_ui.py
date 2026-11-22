from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from orderflow.auth import authenticate, password_record
from orderflow.models import OrderError, Principal

APP = Path(__file__).resolve().parents[2] / "src/app.py"
PASSWORD = "fictional-test-password"


@pytest.fixture
def review_shop(database, monkeypatch):
    with database.begin() as db:
        schema = db.exec_driver_sql("SELECT current_schema()").scalar_one()
        db.execute(
            text("INSERT INTO account_passwords VALUES (:id,:salt,:digest)"),
            [
                {"id": uid, **password_record(PASSWORD)}
                for uid in ["customer-a", "customer-b", "staff-s"]
            ],
        )
    url = database.url.update_query_dict({"options": f"-c search_path={schema}"})
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    return database


def button(app, label):
    return next(item for item in app.button if item.label == label)


def login(app, username, password=PASSWORD):
    app.text_input(key="login_name").set_value(username)
    app.text_input(key="login_password").set_value(password)
    button(app, "Sign in").click().run()
    assert not app.exception


def start(username):
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    login(app, username)
    return app


def test_t20_customer_order_and_shared_browser_switch(review_shop):
    app = start("alex")
    app.radio(key="page").set_value("Place an order").run()
    app.number_input(key="copies").set_value(2)
    app.text_area(key="note").set_value("Collect on Friday")
    button(app, "Place order").click().run()
    assert not app.exception
    assert app.success[0].value == "Order placed."
    assert app.text[0].value == "Collect on Friday"
    assert app.subheader[0].value == "Pending confirmation"
    assert all(item.label != "Confirm order" for item in app.button)
    button(app, "Sign out").click().run()
    assert not app.selectbox
    login(app, "blair")
    assert not app.text
    assert not app.selectbox
    assert app.info[0].value.startswith("Your orders will appear here")


def test_t20_two_staff_sessions_and_handover(review_shop, service):
    customer = Principal("customer-a")
    order = service.create_order(customer, service_id="bw-print", quantity=2)
    first, second = start("sam"), start("sam")
    button(first, "Confirm order").click().run()
    button(second, "Confirm order").click().run()
    assert not second.exception
    assert "Refresh" in second.error[0].value
    assert service.get_order(customer, order.id).order.version == 1
    for label in ["Start production", "Mark ready for pickup"]:
        button(first, label).click().run()
    owner = start("alex")
    assert owner.subheader[0].value == "Ready for pickup"
    assert any("Collect them" in m.value for m in owner.markdown)
    assert all(item.label != "Confirm handover" for item in owner.button)
    button(first, "Confirm handover").click().run()
    button(owner, "Refresh orders").click().run()
    assert owner.subheader[0].value == "Completed"
    assert all(item.label != "Confirm handover" for item in first.button)
    assert len(service.get_order(customer, order.id).history) == 5


def test_t20_invalid_login_and_disabled_session(review_shop):
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    for username in ["sam", "unknown"]:
        login(app, username, "incorrect")
        assert app.error[0].value == "Check your username and password."
        assert not app.selectbox
    login(app, "sam")
    with review_shop.begin() as db:
        db.execute(text("UPDATE users SET active=false WHERE id='staff-s'"))
    button(app, "Refresh orders").click().run()
    assert app.text_input(key="login_name")
    assert not app.selectbox
    with pytest.raises(OrderError) as error:
        authenticate(review_shop, "sam", PASSWORD)
    assert error.value.code == "INVALID_CREDENTIALS"


def test_upgrade_r2_order_with_history(tmp_path, monkeypatch):
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
