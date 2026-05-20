"""Key metrics row component — Chinese UI."""

import streamlit as st
from database.queries import get_24h_aggregates
from utils.formatters import format_usd


def render_metrics():
    st.subheader("📊 关键指标 (最近24小时)")

    agg = get_24h_aggregates()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="总流入",
            value=format_usd(agg["inflow"]),
            help="流入交易所钱包的稳定币总价值",
        )

    with col2:
        st.metric(
            label="总流出",
            value=format_usd(agg["outflow"]),
            help="流出交易所钱包的稳定币总价值",
        )

    with col3:
        net = agg["net_flow"]
        delta = f"{'+' if net > 0 else ''}{format_usd(net)}"
        st.metric(
            label="净流向",
            value=format_usd(abs(net)),
            delta=delta,
            delta_color="normal" if net > 0 else "inverse",
            help="正值 = 资金流出交易所(囤币信号)\n负值 = 资金流入交易所(潜在抛压)",
        )

    with col4:
        st.metric(
            label="大额转账 (>$1M)",
            value=agg["large_tx_count"],
        )

    with col5:
        st.metric(
            label="铸造事件",
            value=agg["mint_count"],
            help="稳定币新铸造次数",
        )
