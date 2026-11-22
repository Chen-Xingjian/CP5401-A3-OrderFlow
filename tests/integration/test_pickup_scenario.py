from datetime import timedelta
from pathlib import Path

from streamlit.testing.v1 import AppTest

from orderflow import scenario
from orderflow.models import Principal

ENTRY = Path(__file__).resolve().parents[2] / "src/scenario_app.py"
SAM = Principal("staff-s")


def click(app, label):
    return next(b for b in app.button if b.label == label).click().run()


def start():
    app = AppTest.from_file(str(ENTRY)).run()
    assert not app.exception and not app.radio
    click(app, "Start demo scenario")
    assert not app.exception
    assert app.radio(key="demo_role").value == "Staff"
    assert app.selectbox(key="demo_user").value == "staff-s"
    return app


def test_t32_isolation_handover_and_restart(database, service, monkeypatch):
    monkeypatch.setenv("ORDERFLOW_DB_PATH", database.url.database)
    owner = Principal("customer-a")
    original = service.create_order(owner, service_id="bw-print", quantity=1)
    snapshot = service.get_order(owner, original.id)
    first, second = start(), start()
    session = first.session_state["pickup_scenario"]
    shop = session.service
    original_path = Path(shop.engine.url.database)
    orders = shop.list_orders(SAM)
    assert {o.owner_id for o in orders} == {"customer-a", "customer-b"}
    histories = {o.owner_id: shop.get_order(SAM, o.id).history for o in orders}
    for user, events in histories.items():
        assert [e.to_status for e in events] == [
            "PENDING",
            "CONFIRMED",
            "PROCESSING",
            "READY_FOR_PICKUP",
        ]
        assert [e.actor_id for e in events] == [user, "staff-s", "staff-s", "staff-s"]
        times = [e.occurred_at for e in events]
        assert times == sorted(set(times))
    assert histories["customer-a"][-1].occurred_at - histories["customer-b"][
        -1
    ].occurred_at == timedelta(hours=50)
    other_ids = {o.id for o in second.session_state["pickup_scenario"].service.list_orders(SAM)}
    assert not other_ids.intersection(o.id for o in orders)
    first.button(key="filter_OVERDUE").click().run()
    click(first, "Confirm handover")
    assert not first.exception
    assert first.button(key="filter_OVERDUE").label == "Pickup overdue (0)"
    assert first.button(key="filter_READY_FOR_PICKUP").label == "Ready for pickup (1)"
    handed = next(o for o in orders if o.owner_id == "customer-b")
    history = shop.get_order(SAM, handed.id).history
    assert history[:-1] == histories["customer-b"] and history[-1].to_status == "COMPLETED"
    click(first, "Restart demo scenario")
    assert not first.exception and not original_path.exists()
    assert first.button(key="filter_OVERDUE").label == "Pickup overdue (1)"
    assert len(first.selectbox(key="chosen").options) == 2
    assert not {o.id for o in orders}.intersection(
        o.id for o in first.session_state["pickup_scenario"].service.list_orders(SAM)
    )
    click(second, "Refresh orders")
    assert second.button(key="filter_READY_FOR_PICKUP").label == "Ready for pickup (2)"
    assert second.button(key="filter_OVERDUE").label == "Pickup overdue (1)"
    assert {
        o.id for o in second.session_state["pickup_scenario"].service.list_orders(SAM)
    } == other_ids
    assert (
        service.list_orders(SAM) == [original] and service.get_order(owner, original.id) == snapshot
    )


def test_t32_failed_restart_preserves_scenario(tmp_path, monkeypatch):
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("ORDERFLOW_DB_PATH", str(shared))
    app = start()
    active = app.session_state["pickup_scenario"]
    with monkeypatch.context() as patch:

        def unavailable(_):
            raise RuntimeError("Fixture preparation failed")

        patch.setattr(scenario.demo, "prepare", unavailable)
        click(app, "Restart demo scenario")
        assert app.error and not app.exception
        assert app.session_state["pickup_scenario"] is active
    app.run()
    assert app.button(key="filter_READY_FOR_PICKUP").label == "Ready for pickup (2)"
    assert not shared.exists()


def test_public_entry_switches_between_shared_shop_and_private_scenario(
    database, service, monkeypatch
):
    monkeypatch.setenv("ORDERFLOW_DB_PATH", database.url.database)
    alex = Principal("customer-a")
    original = service.create_order(alex, service_id="bw-print", quantity=1)
    before = service.get_order(alex, original.id)
    app = AppTest.from_file(str(ENTRY.with_name("app.py"))).run()
    assert app.selectbox(key="chosen").value == str(original.id)
    click(app, "Start demo scenario")
    assert app.selectbox(key="demo_user").value == "staff-s"
    assert app.button(key="filter_READY_FOR_PICKUP").label == "Ready for pickup (2)"
    app.button(key="filter_OVERDUE").click().run()
    click(app, "Confirm handover")
    assert app.button(key="filter_OVERDUE").label == "Pickup overdue (0)"
    click(app, "Return to shop")
    assert not app.exception
    assert app.selectbox(key="demo_user").value == "customer-a"
    assert app.selectbox(key="chosen").value == str(original.id)
    assert service.get_order(alex, original.id) == before
    assert "pickup_scenario" not in app.session_state


def test_customer_pickup_reminders_and_display_names():
    app = start()
    app.radio(key="demo_role").set_value("Customer").run()
    assert "Pickup overdue" not in app.selectbox(key="chosen").options[0]
    assert not app.warning
    assert any(c.value.endswith(" · Alex") for c in app.caption)

    app.selectbox(key="demo_user").set_value("customer-b").run()
    picker = app.selectbox(key="chosen")
    overdue_order = picker.value
    assert len(picker.options) == 1 and "Pickup overdue" in picker.options[0]
    assert "Ready since" in app.warning[0].value
    assert any(c.value.endswith(" · Blair") for c in app.caption)
    assert any(c.value.endswith(" · Sam") for c in app.caption)
    click(app, "Place order")
    assert app.selectbox(key="chosen").value != overdue_order
    assert "Select an order" in app.warning[0].value

    app.radio(key="demo_role").set_value("Staff").run()
    app.selectbox(key="demo_user").set_value("staff-t").run()
    app.button(key="filter_OVERDUE").click().run()
    assert any(c.value == "Customer · Blair" for c in app.caption)
    click(app, "Confirm handover")
    app.radio(key="demo_role").set_value("Customer").run()
    app.selectbox(key="demo_user").set_value("customer-b").run()
    app.selectbox(key="chosen").set_value(overdue_order).run()
    assert not app.exception and not app.warning
    assert all("Pickup overdue" not in option for option in app.selectbox(key="chosen").options)
    events = [c.value.split(" · ")[-1] for c in app.caption if "SGT · " in c.value]
    assert events == ["Taylor", "Sam", "Sam", "Sam", "Blair"]
