"""Dashboard sidebar component."""

import streamlit as st
from config.settings import (
    THRESHOLD_LARGE_TRANSFER, THRESHOLD_EXCHANGE_INFLOW,
    THRESHOLD_WHALE_MOVE, DEFAULT_POLL_INTERVAL_SECONDS,
    DATA_RETENTION_DAYS,
)


def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Configuration")

        # API Keys section
        st.subheader("API Keys")
        etherscan_key = st.text_input(
            "Etherscan API Key",
            type="password",
            value=st.session_state.get("etherscan_key", ""),
            help="Get one free at https://etherscan.io/register",
        )
        if etherscan_key != st.session_state.get("etherscan_key", ""):
            st.session_state["etherscan_key"] = etherscan_key
            import os
            os.environ["ETHERSCAN_API_KEY"] = etherscan_key

        # Thresholds
        st.subheader("⚡ Alert Thresholds")
        threshold_large = st.number_input(
            "Large Transfer (USD)",
            min_value=100_000,
            max_value=100_000_000,
            value=int(st.session_state.get("threshold_large", THRESHOLD_LARGE_TRANSFER)),
            step=100_000,
            format="%d",
        )
        st.session_state["threshold_large"] = threshold_large

        threshold_inflow = st.number_input(
            "Exchange Inflow Single Tx (USD)",
            min_value=500_000,
            max_value=100_000_000,
            value=int(st.session_state.get("threshold_inflow", THRESHOLD_EXCHANGE_INFLOW)),
            step=500_000,
            format="%d",
        )
        st.session_state["threshold_inflow"] = threshold_inflow

        # Poll interval
        st.subheader("🔄 Data Collection")
        poll_interval = st.selectbox(
            "Poll Interval",
            options=[30, 60, 120, 300],
            index=2,  # 120s default
            format_func=lambda x: f"{x} seconds",
        )
        st.session_state["poll_interval"] = poll_interval

        running = st.session_state.get("collector_running", False)
        if st.button("🟢 Start Collecting" if not running else "🔴 Stop Collecting"):
            st.session_state["collector_running"] = not running
            st.rerun()

        status_text = "🟢 Running" if running else "⏸️ Paused"
        st.caption(f"Collector: {status_text}")

        # Data retention
        st.subheader("📊 Data Retention")
        retention_days = st.selectbox(
            "Keep data for",
            options=[7, 30, 90, 180],
            index=2,  # 90 days default
            format_func=lambda x: f"{x} days",
        )
        st.session_state["retention_days"] = retention_days

        st.divider()
        if st.button("🔄 Force Refresh Now"):
            st.session_state["force_refresh"] = True
            st.rerun()

        st.caption(f"On-Chain Monitor v1.0")
