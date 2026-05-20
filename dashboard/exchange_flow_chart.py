"""Exchange flow bar chart component."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from database.queries import get_exchange_flow_timeseries


def render_exchange_flow_chart():
    st.subheader("📈 Exchange Flow (Hourly)")

    data = get_exchange_flow_timeseries(hours=24)

    if not data:
        st.caption("No exchange flow data collected yet. Start the collector to see data.")
        return

    df = pd.DataFrame(data)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["hour"],
        y=df["inflow"],
        name="Inflow (to exchanges)",
        marker_color="#ef4444",  # red for inflow (sell pressure)
        hovertemplate="%{y:$,.0f}<extra>Inflow</extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["hour"],
        y=df["outflow"],
        name="Outflow (from exchanges)",
        marker_color="#22c55e",  # green for outflow (accumulation)
        hovertemplate="%{y:$,.0f}<extra>Outflow</extra>",
    ))

    fig.update_layout(
        barmode="group",
        margin=dict(l=0, r=0, t=10, b=0),
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title=None,
        yaxis_title="USD Value",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)
