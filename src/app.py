"""Streamlit entry point for the OrderFlow campus print shop."""

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from sqlalchemy.exc import ArgumentError, SQLAlchemyError

from orderflow import demo
from orderflow.db import database_path, migration_revision, open_engine
from orderflow.models import OrderError, Principal
from orderflow.rules import CANCELLABLE, NEXT_STATUS, pickup_is_overdue
from orderflow.scenario import PickupScenario
from orderflow.services import OrderService

LABELS = {
    "PENDING": "Pending confirmation",
    "CONFIRMED": "Confirmed",
    "PROCESSING": "In production",
    "READY_FOR_PICKUP": "Ready for pickup",
    "COMPLETED": "Completed",
    "CANCELLED": "Cancelled",
}
QUEUE_FILTERS = {**LABELS, "OVERDUE": "Pickup overdue"}
ACTIONS = {
    "PENDING": "Confirm order",
    "CONFIRMED": "Start production",
    "PROCESSING": "Mark ready for pickup",
    "READY_FOR_PICKUP": "Confirm handover",
}
INSTRUCTIONS = {
    "PENDING": "The print shop has received your order.",
    "CONFIRMED": "The shop has accepted this order for production.",
    "PROCESSING": "Printing is in progress. Please wait for the pickup update.",
    "READY_FOR_PICKUP": "Your prints are ready. Collect them at the print counter.",
    "COMPLETED": "The shop has recorded the handover to the customer.",
    "CANCELLED": "The customer cancelled this order before production.",
}
SG = ZoneInfo("Asia/Singapore")


@st.cache_resource
def connect(path, schema_revision):
    # Streamlit uses both arguments to decide when to prepare the database again.
    engine = open_engine(path)
    demo.prepare(engine)
    return engine


def clear_workspace():
    for key in ("actor", "chosen", "feedback", "queue_filter"):
        st.session_state.pop(key, None)


def change_role():
    clear_workspace()
    st.session_state.pop("demo_user", None)


def show_error(error):
    st.session_state["feedback"] = ("error", str(error))


def new_order(service, actor):
    try:
        order = service.create_order(
            actor,
            service_id=st.session_state[f"item_{actor.user_id}"],
            quantity=st.session_state[f"copies_{actor.user_id}"],
            note=st.session_state[f"note_{actor.user_id}"],
        )
    except OrderError as error:
        show_error(error)
        return
    st.session_state.pop(f"note_{actor.user_id}", None)
    st.session_state.pop(f"copies_{actor.user_id}", None)
    st.session_state["chosen"] = str(order.id)
    st.session_state["feedback"] = ("success", "Order placed.")


def advance(service, order_id, stage, version):
    # These values belong to the page that supplied the clicked button.
    try:
        updated = service.advance_order(
            st.session_state.get("actor"),
            order_id,
            target=NEXT_STATUS[stage],
            expected_version=version,
        )
    except OrderError as error:
        show_error(error)
        return
    st.session_state["feedback"] = (
        "success",
        f"Order updated to {LABELS[updated.status].lower()}.",
    )


def cancel(service, order_id, version):
    try:
        service.cancel_order(st.session_state.get("actor"), order_id, expected_version=version)
    except OrderError as error:
        show_error(error)
        return
    st.session_state["feedback"] = ("success", "Order cancelled.")


def order_form(service, actor):
    st.header("Place an order", anchor=False)
    options = service.available_services(actor)
    if not options:
        st.info("The shop has no services available.")
        return
    with st.form(f"new_order_{actor.user_id}", border=False):
        st.selectbox(
            "Print service", list(options), format_func=options.get, key=f"item_{actor.user_id}"
        )
        st.number_input(
            "Quantity", min_value=1, max_value=99, step=1, key=f"copies_{actor.user_id}"
        )
        st.text_area("Print notes (optional)", max_chars=500, key=f"note_{actor.user_id}")
        st.form_submit_button(
            "Place order",
            on_click=new_order,
            args=(service, actor),
            type="primary",
            width="stretch",
        )


def set_queue_filter(stage):
    st.session_state["queue_filter"] = stage


def queue_filters(orders, overdue):
    counts = Counter(order.status for order in orders)
    counts["OVERDUE"] = len(overdue)
    selected = st.session_state.get("queue_filter")
    with st.container(
        horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"
    ):
        st.markdown("**Current workload**")
        st.button(
            "Clear filter", disabled=selected is None, on_click=set_queue_filter, args=(None,)
        )
    with st.container(horizontal=True, gap="small"):
        for stage, label in QUEUE_FILTERS.items():
            active = stage == selected
            st.button(
                f"{label} ({counts[stage]})",
                key=f"filter_{stage}",
                type="primary" if active else "secondary",
                icon=":material/check:" if active else None,
                on_click=set_queue_filter,
                args=(stage,),
            )
    st.caption(
        f"Pickup overdue: {len(overdue)} of {counts['READY_FOR_PICKUP']} ready for pickup · "
        "48 hours or more since marked ready."
    )
    return selected


def order_list(service, actor, staff):
    with st.container(
        horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"
    ):
        st.header("Shop queue" if staff else "My orders", anchor="order-tracking", width="content")
        st.button("Refresh orders", icon=":material/refresh:")
    as_of = datetime.now(UTC)
    if staff:
        orders, overdue = service.staff_queue(actor, as_of=as_of)
        selected = queue_filters(orders, overdue)
        if selected:
            if selected == "OVERDUE":
                orders = [order for order in orders if order.id in overdue]
            else:
                orders = [order for order in orders if order.status == selected]
            if not orders:
                st.info(f"No orders match the {QUEUE_FILTERS[selected]} filter.")
                return
    else:
        orders, overdue = service.customer_queue(actor, as_of=as_of)
    if not orders:
        st.info(
            "The queue is empty." if staff else "Your orders will appear here after you place one."
        )
        return
    choices = {str(o.id): o for o in orders}

    def label(value):
        o = choices[value]
        stage = LABELS[o.status]
        if o.id in overdue:
            stage += " · Pickup overdue"
        return f"{str(o.id)[:8].upper()} · {o.service_name_snapshot} · {stage}"

    if st.session_state.get("chosen") not in choices:
        st.session_state["chosen"] = next(iter(choices))
    selection = st.selectbox("Select order", list(choices), format_func=label, key="chosen")
    detail = service.get_order(actor, choices[selection].id)
    o = detail.order
    if o.version != choices[selection].version:
        # Refresh labels and reminders if the order changed after we read the queue.
        st.rerun()
    if not staff and overdue and o.id not in overdue:
        st.warning("You have prints awaiting pickup. Select an order marked ‘Pickup overdue’.")
    with st.container(key="receipt"):
        st.subheader(LABELS[o.status], anchor=False)
        st.write(INSTRUCTIONS[o.status])
        if o.status == "READY_FOR_PICKUP":
            ready_at = detail.history[-1].occurred_at
            if pickup_is_overdue(ready_at, as_of):
                st.warning(
                    f"Pickup overdue · Ready since {ready_at.astimezone(SG):%d %b %Y, %H:%M} SGT."
                )

        first, second = st.columns([3, 1])
        first.caption("Print service")
        first.write(o.service_name_snapshot)
        second.caption("Quantity")
        second.write(str(o.quantity))
        st.caption(f"Order ID · {o.id}")
        if staff:
            st.caption(f"Customer · {detail.owner_name.title()}")
        if o.note:
            st.markdown("**Print notes**")
            st.text(o.note)
        if not staff and o.status in CANCELLABLE:
            st.caption("You can cancel this order until production starts.")
            st.button(
                "Cancel order",
                key=f"cancel_{o.id}_{o.version}",
                on_click=cancel,
                args=(service, o.id, o.version),
            )
        if staff and o.status in NEXT_STATUS:
            if o.status == "READY_FOR_PICKUP":
                st.write("Confirm only after you have handed the prints to the customer.")
            st.button(
                ACTIONS[o.status],
                type="primary",
                key=f"advance_{o.id}_{o.version}",
                on_click=advance,
                args=(service, o.id, o.status, o.version),
            )
    with st.container(key="history"):
        st.subheader("Order history", anchor=False)
        for item in reversed(detail.history):
            source = LABELS[item.from_status] if item.from_status else "Order created"
            with st.container(key=f"event_{item.sequence}", gap=None):
                st.write(f"{source} → {LABELS[item.to_status]}")
                st.caption(
                    f"{item.occurred_at.astimezone(SG):%d %b %Y, %H:%M} SGT · {item.actor_name.title()}"
                )


def shared_shop():
    return OrderService(connect(database_path(), migration_revision()))


def switch_shop(role, user):
    clear_workspace()
    for key in list(st.session_state):
        if key.startswith(("item_", "copies_", "note_")):
            del st.session_state[key]
    st.session_state["demo_role"] = role
    st.session_state["demo_user"] = user
    st.rerun()


def scenario_service(*, include_shop=False):
    scenario = st.session_state.get("pickup_scenario")
    with st.container(border=True):
        st.markdown("**Pickup demonstration**")
        if scenario is None:
            st.write("Start a private shop with two ready orders. One has waited 50 hours.")
        else:
            st.caption("Only this session uses these orders. Restart to create a fresh pair.")
        if st.button("Start demo scenario" if scenario is None else "Restart demo scenario"):
            try:
                replacement = PickupScenario()
            except (OSError, SQLAlchemyError, OrderError, RuntimeError):
                st.error("Could not prepare the new scenario. Please try again.")
                return scenario.service if scenario is not None else None
            st.session_state["pickup_scenario"] = replacement
            if scenario is not None:
                scenario.close()
            switch_shop("Staff", "staff-s")
        if scenario is not None and include_shop and st.button("Return to shop"):
            del st.session_state["pickup_scenario"]
            scenario.close()
            switch_shop("Customer", "customer-a")
    return scenario.service if scenario is not None else None


def combined_shop():
    return scenario_service(include_shop=True) or shared_shop()


def main(get_service=combined_shop):
    st.set_page_config(page_title="OrderFlow · Campus print shop", page_icon="📄", layout="wide")
    st.html(Path(__file__).with_name("workspace.css"))
    with st.container(key="masthead"):
        identity, role_control, user_control = st.columns(
            [2.1, 1.2, 1], vertical_alignment="center"
        )
        with identity:
            st.title("OrderFlow", anchor=False)
            st.caption("Campus print shop · Fictional demo accounts")
    try:
        service = get_service()
        if service is None:
            return
        role = role_control.radio(
            "Demo role",
            ["Customer", "Staff"],
            horizontal=True,
            key="demo_role",
            on_change=change_role,
        )
        users = demo.choices(service.engine, role.upper())
        if not users:
            clear_workspace()
            st.info("No active demo users are available for this role.")
            return
        if st.session_state.get("demo_user") not in users:
            clear_workspace()
            st.session_state["demo_user"] = next(iter(users))
        selected = user_control.selectbox(
            "Demo user",
            list(users),
            format_func=users.get,
            key="demo_user",
            on_change=clear_workspace,
        )
        actor = Principal(selected)
        st.session_state["actor"] = actor
        if service.account_role(actor) != role.upper():
            clear_workspace()
            st.warning("This demo account changed. Select an active account.")
            return
        if feedback := st.session_state.pop("feedback", None):
            kind, message = feedback
            (st.success if kind == "success" else st.error)(message)
        if role == "Customer":
            st.html('<a class="order-jump" href="#order-tracking">Jump to my orders ↓</a>')
            create, track = st.columns([0.85, 1.35], gap="medium")
            with create.container(key="create_panel"):
                order_form(service, actor)
        else:
            track = st
        with track.container(key="track_panel"):
            order_list(service, actor, role == "Staff")
    except OrderError as error:
        st.error(str(error))
    except (ValueError, OSError, ArgumentError, SQLAlchemyError, RuntimeError):
        st.error("The demo database is unavailable. Check its connection and migrations.")


if __name__ == "__main__":
    main()
