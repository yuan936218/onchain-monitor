"""Mint/burn events timeline component."""

import streamlit as st
from database.queries import get_recent_mint_burns
from utils.formatters import format_usd, format_token_amount, format_timestamp


def render_mint_burn_timeline():
    st.subheader("🏦 Stablecoin Mint / Burn Events")

    events = get_recent_mint_burns(hours=48)

    if not events:
        st.info("No mint/burn events detected yet.")
        return

    for event in events[:20]:
        icon = "🟢" if event.event_type == "mint" else "🔴"
        action = "minted" if event.event_type == "mint" else "burned"

        with st.container():
            st.markdown(
                f"{icon} **{format_token_amount(event.value, event.token_symbol)}** {action} "
                f"({format_usd(event.value_usd)})"
            )
            st.caption(f"{format_timestamp(event.block_timestamp)} — TX: {event.tx_hash[:10]}...")
            st.divider()
