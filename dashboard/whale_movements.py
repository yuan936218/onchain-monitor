"""Whale movements tracking component — Chinese UI."""

import streamlit as st
from database.queries import get_whale_movements
from utils.formatters import format_usd, format_token_amount, format_timestamp, format_address


def render_whale_movements():
    st.subheader("🐋 巨鲸动向")

    movements = get_whale_movements(hours=24)

    if not movements:
        st.info("暂无巨鲸动向数据。")
        return

    for m in movements[:20]:
        from_info = m.from_label or format_address(m.from_address)
        to_info = m.to_label or format_address(m.to_address)

        direction = ""
        if m.to_label:
            direction = " ⚠️ 巨鲸 → 交易所"
        elif m.from_label:
            direction = " 📤 交易所 → 巨鲸"

        with st.container():
            st.markdown(
                f"**{format_token_amount(m.value, m.asset)}** "
                f"({format_usd(m.value_usd)})"
            )
            st.caption(f"{from_info} → {to_info}{direction}")
            st.caption(f"{format_timestamp(m.block_timestamp)}")
            tx_url = f"https://etherscan.io/tx/{m.tx_hash}"
            st.link_button("↗ 查看交易", tx_url)
            st.divider()
