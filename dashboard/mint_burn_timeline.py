"""Mint/burn events timeline component — Chinese UI."""

import streamlit as st
from database.queries import get_recent_mint_burns
from utils.formatters import format_usd, format_token_amount, format_timestamp, get_explorer_tx_url


def render_mint_burn_timeline():
    st.subheader("🏦 稳定币铸造/销毁")

    sel_chain = st.session_state.get("selected_chain", "all")
    chain = None if sel_chain == "all" else sel_chain

    events = get_recent_mint_burns(hours=48, chain=chain)

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
            st.caption(f"{format_timestamp(event.block_timestamp)}")
            tx_url = get_explorer_tx_url(event.chain, event.tx_hash)
            st.link_button("↗ 查看交易", tx_url)
            st.divider()
