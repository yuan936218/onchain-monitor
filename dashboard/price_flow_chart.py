"""Price vs Exchange Net Flow correlation chart — Chinese UI."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from plotly.subplots import make_subplots


def render_price_flow_chart():
    st.subheader("💹 价格与资金流向关联")

    from database.queries import get_price_history, get_hourly_flow_patterns

    sel_chain = st.session_state.get("selected_chain", "all")
    chain = None if sel_chain == "all" else sel_chain

    col1, col2 = st.columns(2)
    with col1:
        hours = st.selectbox(
            "时间范围", options=[6, 12, 24, 48, 72],
            index=2, format_func=lambda x: f"最近 {x} 小时",
            key="price_flow_hours",
        )
    with col2:
        token_id = st.selectbox(
            "价格标的", options=["ETH", "WBTC"],
            format_func=lambda x: f"{x} 价格",
            key="price_token",
        )

    prices = get_price_history(hours=max(hours, 24), token_id=token_id)
    patterns = get_hourly_flow_patterns(days=max(hours // 24, 1), chain=chain)

    if not prices:
        st.info("暂无价格数据。价格每15分钟采集一次，请稍后查看。")
        return

    df_price = pd.DataFrame(prices)

    # Aggregate flows to match price snapshot times (hourly buckets)
    hourly_flows = {}
    for p in patterns:
        hourly_flows[p["hour"]] = p
    hourly_df = pd.DataFrame([
        {"hour": h, "net_flow": f["avg_outflow"] - f["avg_inflow"]}
        for h, f in hourly_flows.items()
    ])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Price line (primary y-axis)
    fig.add_trace(
        go.Scatter(
            x=df_price["snapshot_at"], y=df_price["price_usd"],
            name=f"{token_id} 价格",
            mode="lines",
            line=dict(color="#3b82f6", width=2),
            hovertemplate="$%{y:,.2f}<extra>价格</extra>",
        ),
        secondary_y=False,
    )

    # Net flow bars (secondary y-axis) — aggregate per hour
    if not hourly_df.empty:
        net_max = hourly_df["net_flow"].abs().max() or 1
        bar_colors = np.where(hourly_df["net_flow"] >= 0, "#22c55e", "#ef4444")
        fig.add_trace(
            go.Bar(
                x=[f"{h:02d}:00" for h in hourly_df["hour"]],
                y=hourly_df["net_flow"],
                name="交易所净流量",
                marker_color=bar_colors,
                opacity=0.6,
                hovertemplate="%{y:$,.0f}<extra>净流量</extra>",
            ),
            secondary_y=True,
        )

    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        template="plotly_white",
    )
    fig.update_yaxes(title_text=f"{token_id} 价格 (USD)", secondary_y=False)
    fig.update_yaxes(title_text="交易所净流量 (USD)", secondary_y=True)

    st.plotly_chart(fig, use_container_width=True)

    # Correlation insight
    if len(prices) >= 3:
        first_price = prices[0]["price_usd"]
        last_price = prices[-1]["price_usd"]
        price_change = (last_price - first_price) / first_price * 100

        total_net = hourly_df["net_flow"].sum() if not hourly_df.empty else 0
        flow_direction = "净流出" if total_net > 0 else "净流入"

        st.caption(
            f"📊 期间 {token_id} 价格变化: {price_change:+.2f}% | "
            f"交易所累计{flow_direction}: ${abs(total_net):,.0f} | "
            f"提示: 大额流入+价格下跌 = 潜在抛售信号; 大额流出+价格上涨 = 囤币看涨信号"
        )
