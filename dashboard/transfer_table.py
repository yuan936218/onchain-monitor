"""Large transfers sortable table component."""

import streamlit as st
import pandas as pd
from database.queries import get_large_transfers
from utils.formatters import format_usd, format_token_amount, format_timestamp, format_address
from config.settings import STABLECOIN_TOKENS


def render_transfer_table():
    st.subheader("📋 Recent Large Transfers")

    col1, col2, col3 = st.columns(3)
    with col1:
        hours = st.selectbox("Time range", options=[1, 6, 12, 24, 72], index=3, format_func=lambda x: f"Last {x}h")
    with col2:
        token_filter = st.selectbox("Token", options=["ALL", "USDT", "USDC"])
    with col3:
        min_val = st.number_input("Min value (USD)", min_value=100_000, max_value=100_000_000, value=500_000, step=100_000, format="%d")

    transfers = get_large_transfers(hours=hours, min_value_usd=min_val, token_filter=token_filter)

    if not transfers:
        st.info("No large transfers found for the selected criteria.")
        return

    rows = []
    for t in transfers:
        from_info = t.from_label or format_address(t.from_address)
        to_info = t.to_label or format_address(t.to_address)
        rows.append({
            "Time": format_timestamp(t.block_timestamp),
            "Token": t.token_symbol,
            "From": from_info,
            "To": to_info,
            "Amount": format_token_amount(t.value, t.token_symbol),
            "USD Value": format_usd(t.value_usd),
            "TX": f"https://etherscan.io/tx/{t.tx_hash}",
        })

    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "TX": st.column_config.LinkColumn("TX", display_text="↗"),
        }
    )

    # CSV export
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"onchain_transfers_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )
