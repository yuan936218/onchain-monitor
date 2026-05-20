"""Mint/burn events timeline component — Chinese UI."""

import streamlit as st
from database.queries import get_recent_mint_burns
from utils.formatters import format_usd, format_token_amount, format_timestamp


def render_mint_burn_timeline():
    st.subheader("🏦 稳定币铸造/销毁")

    events = get_recent_mint_burns(hours=48)

    if not events:
        st.info("暂无铸造/销毁事件。采集器每轮检测 >$1M 的供应量变化，通常需要较长时间积累。")
        return

    for event in events[:20]:
        icon = "🟢" if event.event_type == "mint" else "🔴"
        action = "铸造" if event.event_type == "mint" else "销毁"

        with st.container():
            st.markdown(
                f"{icon} **{format_token_amount(event.value, event.token_symbol)}** 被{action} "
                f"({format_usd(event.value_usd)})"
            )
            st.caption(f"{format_timestamp(event.block_timestamp)} — {event.tx_hash[:10]}...")
            st.divider()
