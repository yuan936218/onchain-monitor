"""Whale movements tracking component — Chinese UI."""

import streamlit as st
from database.queries import get_whale_movements, get_large_transfers
from utils.formatters import format_usd, format_token_amount, format_timestamp, format_address, get_explorer_tx_url


def render_whale_movements():
    st.subheader("🐋 巨鲸动向")

    sel_chain = st.session_state.get("selected_chain", "all")
    chain = None if sel_chain == "all" else sel_chain

    movements = get_whale_movements(hours=24, chain=chain)

    # Fall back to large transfers (>$10M) if no whale-specific records
    if not movements:
        large = get_large_transfers(hours=72, min_value_usd=10_000_000, token_filter=None, chain=chain)
        if large:
            st.caption("基于大额转账 (>$10M) 的巨鲸活动推断：")
            for t in large[:15]:
                from_info = t.from_label or format_address(t.from_address)
                to_info = t.to_label or format_address(t.to_address)
                direction = " ⚠️ → 交易所" if t.to_label else (" 📤 交易所 →" if t.from_label else "")

                with st.container():
                    st.markdown(
                        f"**{format_token_amount(t.value, t.token_symbol)}** "
                        f"({format_usd(t.value_usd)})"
                    )
                    st.caption(f"{from_info} → {to_info}{direction}")
                    st.caption(f"{format_timestamp(t.detected_at)}")
                    tx_url = get_explorer_tx_url(t.chain, t.tx_hash)
                    st.link_button("↗ 查看交易", tx_url)
                    st.divider()
            return

        st.info("暂无巨鲸动向数据。监控地址库中的鲸鱼地址 (Vitalik、Wintermute 等) 近期无交易所交互。")
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
            st.caption(f"{format_timestamp(m.detected_at)}")
            tx_url = get_explorer_tx_url(m.chain, m.tx_hash)
            st.link_button("↗ 查看交易", tx_url)
            st.divider()
