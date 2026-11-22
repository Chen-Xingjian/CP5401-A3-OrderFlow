"""Streamlit Community Cloud entry point for the private pickup scenario."""

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app import clear_workspace, main
from orderflow.models import OrderError
from orderflow.scenario import PickupScenario


def scenario_service():
    scenario = st.session_state.get("pickup_scenario")
    with st.container(border=True):
        st.subheader("Pickup demonstration", anchor=False)
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
            clear_workspace()
            for key in list(st.session_state):
                if key.startswith(("item_", "copies_", "note_")):
                    del st.session_state[key]
            st.session_state["demo_role"] = "Staff"
            st.session_state["demo_user"] = "staff-s"
            st.rerun()
    return scenario.service if scenario is not None else None


if __name__ == "__main__":
    main(scenario_service)
