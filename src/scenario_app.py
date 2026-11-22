"""Optional scenario-only Streamlit entry point."""

from app import main, scenario_service

if __name__ == "__main__":
    main(scenario_service)
