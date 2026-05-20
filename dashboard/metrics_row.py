"""Key metrics row component."""

import streamlit as st
from database.queries import get_24h_aggregates
from utils.formatters import format_usd


def render_metrics():
    st.subheader("📊 Key Metrics (Last 24 Hours)")

    agg = get_24h_aggregates()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Total Inflow",
            value=format_usd(agg["inflow"]),
            help="Stablecoin value moved INTO exchange wallets",
        )

    with col2:
        st.metric(
            label="Total Outflow",
            value=format_usd(agg["outflow"]),
            help="Stablecoin value moved OUT of exchange wallets",
        )

    with col3:
        net = agg["net_flow"]
        delta = f"{'+' if net > 0 else ''}{format_usd(net)}"
        st.metric(
            label="Net Flow",
            value=format_usd(abs(net)),
            delta=delta,
            delta_color="normal" if net > 0 else "inverse",
            help="Positive = more outflow (accumulation). Negative = more inflow (sell pressure).",
        )

    with col4:
        st.metric(
            label="Large Transfers (>$1M)",
            value=agg["large_tx_count"],
        )

    with col5:
        st.metric(
            label="Mint Events",
            value=agg["mint_count"],
            help="Number of new stablecoins minted",
        )
