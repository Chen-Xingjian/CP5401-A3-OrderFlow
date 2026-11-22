"""Streamlit entry point for the OrderFlow campus print shop."""

import os
from zoneinfo import ZoneInfo

import streamlit as st
from sqlalchemy.exc import ArgumentError

from orderflow.auth import authenticate
from orderflow.db import open_engine
from orderflow.models import OrderError
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
def connect(url):
    return open_engine(url, pool_pre_ping=True)


def clear_session():
    for key in list(st.session_state):
        del st.session_state[key]


def show_error(error):
    if error.code == "UNAUTHENTICATED":
        clear_session()
    st.session_state["feedback"] = ("error", str(error))


def sign_in(engine):
    name = st.session_state["login_name"]
    password = st.session_state.pop("login_password", "")
    try:
        actor = authenticate(engine, name, password)
    except OrderError as error:
        show_error(error)
        return
    clear_session()
    st.session_state["actor"] = actor


def new_order(service):
    try:
        order = service.create_order(
            st.session_state.actor,
            service_id=st.session_state.item,
            quantity=st.session_state.copies,
            note=st.session_state.note,
        )
    except OrderError as error:
        show_error(error)
        return
    st.session_state["chosen"] = str(order.id)
    st.session_state["page"] = "My orders"
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
    with st.form("new_order"):
        st.selectbox("Print service", list(options), format_func=options.get, key="item")
        st.number_input("Quantity", min_value=1, max_value=99, step=1, key="copies")
        st.text_area("Print notes (optional)", max_chars=500, key="note")
        st.form_submit_button("Place order", on_click=new_order, args=(service,), type="primary")


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
    st.caption("Campus print shop")
    url = os.getenv("DATABASE_URL")
    if not url:
        st.error("OrderFlow needs a configured database connection.")
        return
    try:
        service = OrderService(connect(url))
    except (ValueError, ArgumentError):
        st.error("Check the database connection configuration.")
        return
    if feedback := st.session_state.pop("feedback", None):
        kind, message = feedback
        (st.success if kind == "success" else st.error)(message)
    actor = st.session_state.get("actor")
    if actor is None:
        st.header("Sign in")
        with st.form("login"):
            st.text_input("Username", key="login_name")
            st.text_input("Password", type="password", key="login_password")
            st.form_submit_button(
                "Sign in", type="primary", on_click=sign_in, args=(service.engine,)
            )
        return
    try:
        role = service.account_role(actor)
        staff = role == "STAFF"
        st.sidebar.subheader("Account")
        st.sidebar.write(f"{actor.user_id} · {'Staff' if staff else 'Customer'}")
        st.sidebar.button("Refresh orders")
        st.sidebar.button("Sign out", on_click=clear_session)
        if not staff:
            page = st.radio(
                "Workspace", ["My orders", "Place an order"], horizontal=True, key="page"
            )
            if page == "Place an order":
                order_form(service, actor)
                return
        order_list(service, actor, staff)
    except OrderError as error:
        if error.code == "UNAUTHENTICATED":
            show_error(error)
            st.rerun()
        st.error(str(error))


main()
