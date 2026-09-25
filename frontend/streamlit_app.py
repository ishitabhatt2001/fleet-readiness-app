"""
Naval Fleet Readiness & Maintenance Intelligence Platform - Streamlit frontend.

Run locally (with the FastAPI backend already running on port 8000):
    streamlit run frontend/streamlit_app.py

Set API_BASE_URL in your environment (or .env) if the backend isn't on
localhost:8000 - e.g. when both are running as separate Docker containers.
"""

import os
import requests
import pandas as pd
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Fleet Readiness Dashboard", layout="wide")
st.title("🚢 Naval Fleet Readiness & Maintenance Dashboard")
st.caption(f"Backend: {API_BASE_URL}")


def fetch(path: str):
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach backend at {API_BASE_URL}{path}: {e}")
        return []


tab1, tab2, tab3 = st.tabs(["Vessel Positions", "Maintenance & Readiness", "Ask a Question"])

with tab1:
    st.subheader("Latest Vessel Positions")
    vessels = fetch("/vessels/")
    if vessels:
        df = pd.DataFrame(vessels)
        st.dataframe(df, use_container_width=True)
        st.map(df.rename(columns={"lat": "latitude", "lon": "longitude"}))

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Recent Maintenance Events")
        events = fetch("/maintenance/events")
        if events:
            st.dataframe(pd.DataFrame(events), use_container_width=True)
    with col2:
        st.subheader("Current Readiness Status")
        readiness = fetch("/maintenance/readiness")
        if readiness:
            df_r = pd.DataFrame(readiness)
            st.dataframe(df_r, use_container_width=True)
            st.bar_chart(df_r.set_index("vessel_id")["readiness_score"])

with tab3:
    st.subheader("Ask the fleet a question")
    question = st.text_input(
        "e.g. Which vessels are due for maintenance in the next 30 days?"
    )
    if st.button("Ask") and question:
        try:
            resp = requests.post(
                f"{API_BASE_URL}/query/", json={"question": question}, timeout=15
            )
            resp.raise_for_status()
            st.write(resp.json()["answer"])
        except requests.exceptions.RequestException as e:
            st.error(f"Request failed: {e}")
