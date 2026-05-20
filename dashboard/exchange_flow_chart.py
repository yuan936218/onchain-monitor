"""Exchange flow bar chart component — Chinese UI."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from database.queries import get_exchange_flow_timeseries


def render_exchange_flow_chart():
    st.subheader("📈 交易所资金流向 (按小时)")

    data = get_exchange_flow_timeseries(hours=24)

    if not data:
        st.caption("暂无交易所流量数据，请先启动采集器。")
        return

    df = pd.DataFrame(data)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["hour"],
        y=df["inflow"],
        name="流入交易所",
        marker_color="#ef4444",
        hovertemplate="%{y:$,.0f}<extra>流入</extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["hour"],
        y=df["outflow"],
        name="流出交易所",
        marker_color="#22c55e",
        hovertemplate="%{y:$,.0f}<extra>流出</extra>",
    ))

    fig.update_layout(
        barmode="group",
        margin=dict(l=0, r=0, t=10, b=0),
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title=None,
        yaxis_title="美元价值",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)
