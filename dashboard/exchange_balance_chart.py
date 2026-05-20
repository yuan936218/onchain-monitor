"""Exchange balance time-series chart — Chinese UI."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.formatters import format_usd


def render_exchange_balance_chart():
    from database.queries import get_exchange_balance_timeseries

    st.subheader("🏦 交易所余额变化")

    sel_chain = st.session_state.get("selected_chain", "all")
    chain = None if sel_chain == "all" else sel_chain
    global_token = st.session_state.get("selected_token", "ALL")

    col1, col2 = st.columns(2)
    with col1:
        hours = st.selectbox(
            "时间范围", options=[6, 12, 24, 48],
            index=2, format_func=lambda x: f"最近 {x} 小时",
            key="balance_hours",
        )
    with col2:
        token_filter = st.selectbox(
            "币种", options=["ALL", "USDT", "USDC", "ETH", "WBTC"],
            index=["ALL", "USDT", "USDC", "ETH", "WBTC"].index(global_token) if global_token in ["ALL", "USDT", "USDC", "ETH", "WBTC"] else 0,
            key="balance_token",
            format_func=lambda x: "全部" if x == "ALL" else x,
        )

    balances = get_exchange_balance_timeseries(
        hours=hours, chain=chain,
        token_filter=None if token_filter == "ALL" else token_filter,
    )

    if not balances:
        st.info("暂无交易所余额数据。余额每15分钟采集一次，请稍后再查看。")
        return

    fig = go.Figure()

    colors = {
        "Binance": "#F0B90B",
        "Coinbase": "#0052FF",
        "OKX": "#000000",
        "Kraken": "#5741D9",
        "Bitfinex": "#AECB56",
        "Bybit": "#F7A600",
        "Huobi": "#2CA6E0",
        "Gate.io": "#D35C5C",
    }

    for exchange_name, points in sorted(balances.items()):
        if not points:
            continue
        df = pd.DataFrame(points)
        color = colors.get(exchange_name, None)
        fig.add_trace(go.Scatter(
            x=df["snapshot_at"],
            y=df["balance_usd"],
            mode="lines+markers",
            name=exchange_name,
            line=dict(width=2, color=color),
            marker=dict(size=4, color=color),
            hovertemplate=f"{exchange_name}<br>%{{x}}<br>余额: %{{y:$,.0f}}<extra></extra>",
        ))

    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis_title=None,
        yaxis_title="余额 (USD)",
        yaxis_tickprefix="$",
        hovermode="x unified",
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary insight
    if balances:
        latest_totals = {}
        for name, pts in balances.items():
            if pts:
                latest_totals[name] = pts[-1]["balance_usd"]

        if latest_totals:
            top = sorted(latest_totals.items(), key=lambda x: x[1], reverse=True)
            total = sum(v for _, v in top)
            parts = [f"{n}: {format_usd(v)}" for n, v in top[:3]]
            st.caption(f"最新余额合计: {format_usd(total)} | 占比前三: {' · '.join(parts)}")
