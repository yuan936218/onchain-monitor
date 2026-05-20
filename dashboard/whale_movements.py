"""Whale movements tracking component."""

import streamlit as st
from database.queries import get_whale_movements
from utils.formatters import format_usd, format_token_amount, format_timestamp, format_address


def render_whale_movements():
    st.subheader("🐋 Whale Movements")

    movements = get_whale_movements(hours=24)

    if not movements:
        st.info("No whale movements detected yet.")
        return

    for m in movements[:20]:
        from_info = m.from_label or format_address(m.from_address)
        to_info = m.to_label or format_address(m.to_address)

        # Highlight exchange-related moves
        direction = ""
        if m.to_label:
            direction = " ⚠️ Whale → Exchange"
        elif m.from_label:
            direction = " 📤 Exchange → Whale"

        with st.container():
            st.markdown(
                f"**{format_token_amount(m.value, m.asset)}** "
                f"({format_usd(m.value_usd)})"
            )
            st.caption(f"{from_info} → {to_info}{direction}")
            st.caption(f"{format_timestamp(m.block_timestamp)}")
            tx_url = f"https://etherscan.io/tx/{m.tx_hash}"
            st.link_button("↗ View TX", tx_url)
            st.divider()
