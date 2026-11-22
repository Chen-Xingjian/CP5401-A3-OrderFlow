"""Streamlit entry point for the OrderFlow campus print shop."""

from zoneinfo import ZoneInfo

import streamlit as st
from sqlalchemy.exc import ArgumentError, SQLAlchemyError

from orderflow import demo
from orderflow.db import database_path, open_engine
from orderflow.models import OrderError, Principal
from orderflow.rules import NEXT_STATUS
from orderflow.services import OrderService

LABELS = {
    "PENDING": "Pending confirmation",
    "CONFIRMED": "Confirmed",
    "PROCESSING": "In production",
    "READY_FOR_PICKUP": "Ready for pickup",
    "COMPLETED": "Completed",
}
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
}
SG = ZoneInfo("Asia/Singapore")


@st.cache_resource
def connect(path):
    engine = open_engine(path)
    demo.prepare(engine)
    return engine


def clear_workspace():
    for key in ("actor", "chosen", "feedback"):
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


def order_form(service, actor):
    st.header("Place an order")
    options = service.available_services(actor)
    if not options:
        st.info("The shop has no services available.")
        return
    with st.form(f"new_order_{actor.user_id}"):
        st.selectbox(
            "Print service", list(options), format_func=options.get, key=f"item_{actor.user_id}"
        )
        st.number_input(
            "Quantity", min_value=1, max_value=99, step=1, key=f"copies_{actor.user_id}"
        )
        st.text_area("Print notes (optional)", max_chars=500, key=f"note_{actor.user_id}")
        st.form_submit_button(
            "Place order", on_click=new_order, args=(service, actor), type="primary"
        )


def order_list(service, actor, staff):
    st.header("Shop queue" if staff else "My orders")
    orders = service.list_orders(actor)
    if not orders:
        st.info(
            "The queue is empty." if staff else "Your orders will appear here after you place one."
        )
        return
    choices = {str(o.id): o for o in orders}

    def label(value):
        o = choices[value]
        return f"{str(o.id)[:8].upper()} · {o.service_name_snapshot} · {LABELS[o.status]}"

    if st.session_state.get("chosen") not in choices:
        st.session_state["chosen"] = next(iter(choices))
    selection = st.selectbox("Select order", list(choices), format_func=label, key="chosen")
    detail = service.get_order(actor, choices[selection].id)
    o = detail.order
    with st.container(border=True):
        st.subheader(LABELS[o.status])
        st.write(INSTRUCTIONS[o.status])
        first, second = st.columns([3, 1])
        first.metric("Print service", o.service_name_snapshot)
        second.metric("Quantity", o.quantity)
        st.caption(f"Order ID · {o.id}")
        if staff:
            st.caption(f"Customer · {o.owner_id}")
        if o.note:
            st.markdown("**Print notes**")
            st.text(o.note)
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
    st.subheader("Order history")
    for item in reversed(detail.history):
        source = LABELS[item.from_status] if item.from_status else "Order created"
        st.write(f"{source} → {LABELS[item.to_status]}")
        st.caption(f"{item.occurred_at.astimezone(SG):%d %b %Y, %H:%M} SGT · {item.actor_id}")


def main():
    st.set_page_config(page_title="OrderFlow · Campus print shop", page_icon="📄")
    st.title("OrderFlow")
    st.caption("Campus print shop · Demo workspace with fictional accounts")
    try:
        service = OrderService(connect(database_path()))
        role = st.radio(
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
        selected = st.selectbox(
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
            order_form(service, actor)
        st.button("Refresh orders")
        order_list(service, actor, role == "Staff")
    except OrderError as error:
        st.error(str(error))
    except (ValueError, OSError, ArgumentError, SQLAlchemyError, RuntimeError):
        st.error("The demo database is unavailable. Check its connection and migrations.")


main()
