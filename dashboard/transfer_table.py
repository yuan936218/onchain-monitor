"""Large transfers sortable table component — Chinese UI."""

import streamlit as st
import pandas as pd
from database.queries import get_large_transfers
from utils.formatters import format_usd, format_token_amount, format_timestamp, format_address, get_explorer_tx_url


def render_transfer_table():
    st.subheader("📋 大额转账记录")

    sel_chain = st.session_state.get("selected_chain", "all")
    chain = None if sel_chain == "all" else sel_chain

    col1, col2, col3 = st.columns(3)
    with col1:
        hours = st.selectbox(
            "时间范围", options=[1, 6, 12, 24, 72],
            index=3, format_func=lambda x: f"最近 {x} 小时",
        )
    with col2:
        token_filter = st.selectbox("币种", options=["ALL", "USDT", "USDC"], format_func=lambda x: "全部" if x == "ALL" else x)
    with col3:
        min_val = st.number_input(
            "最低金额 (USD)", min_value=10_000, max_value=100_000_000,
            value=100_000, step=10_000, format="%d",
        )

    transfers = get_large_transfers(hours=hours, min_value_usd=min_val, token_filter=token_filter, chain=chain)

    if not transfers:
        st.info("当前筛选条件下没有找到大额转账记录。")
        return

    rows = []
    for t in transfers:
        from_info = t.from_label or format_address(t.from_address)
        to_info = t.to_label or format_address(t.to_address)
        rows.append({
            "时间": format_timestamp(t.block_timestamp),
            "币种": t.token_symbol,
            "发送方": from_info,
            "接收方": to_info,
            "数量": format_token_amount(t.value, t.token_symbol),
            "美元价值": format_usd(t.value_usd),
            "交易": get_explorer_tx_url(t.chain, t.tx_hash),
        })

    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "交易": st.column_config.LinkColumn("交易", display_text="↗ 查看"),
        }
    )

    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 导出CSV",
        data=csv,
        file_name=f"链上转账_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )
