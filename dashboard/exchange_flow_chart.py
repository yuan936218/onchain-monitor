"""Exchange flow bar chart component — Chinese UI."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from database.queries import get_exchange_flow_timeseries


def render_exchange_flow_chart():
    st.subheader("📈 交易所资金流向 (按小时)")

    data = get_exchange_flow_timeseries(hours=24)

    if not data:
        st.caption("暂无交易所流量数据，请先启动采集器。")
        return

    df = pd.DataFrame(data)
    df["net_flow"] = df["outflow"] - df["inflow"]
    net_colors = np.where(df["net_flow"] >= 0, "#22c55e", "#ef4444")

    fig = go.Figure()

    # Bars: inflow / outflow
    fig.add_trace(go.Bar(
        x=df["hour"], y=df["inflow"],
        name="流入交易所",
        marker_color="#ef4444",
        hovertemplate="%{y:$,.0f}<extra>流入</extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["hour"], y=df["outflow"],
        name="流出交易所",
        marker_color="#22c55e",
        hovertemplate="%{y:$,.0f}<extra>流出</extra>",
    ))

    # Net flow line
    fig.add_trace(go.Scatter(
        x=df["hour"], y=df["net_flow"],
        name="净流量",
        mode="lines+markers",
        line=dict(color="#fbbf24", width=2),
        marker=dict(color=net_colors, size=6),
        yaxis="y2",
        hovertemplate="%{y:$,.0f}<extra>净流量</extra>",
    ))

    # Zero reference line
    fig.add_hline(y=0, line_dash="dot", line_color="#6b7280", opacity=0.4, yref="y2")

    fig.update_layout(
        barmode="group",
        margin=dict(l=0, r=0, t=10, b=0),
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title=None,
        yaxis=dict(title="毛流量 (USD)"),
        yaxis2=dict(
            title="净流量 (USD)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        hovermode="x unified",
    )

    # Summary insight
    total_net = df["net_flow"].sum()
    if total_net > 0:
        st.caption(f"📊 24h 净流出 {total_net:+,.0f} USD → 资金倾向流出交易所（囤币信号）")
    elif total_net < 0:
        st.caption(f"📊 24h 净流入 {total_net:+,.0f} USD → 资金倾向流入交易所（潜在抛压）")
    else:
        st.caption("📊 24h 净流量 0 USD → 交易所资金流向平衡")

    st.plotly_chart(fig, use_container_width=True)
