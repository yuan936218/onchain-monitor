"""Hourly flow pattern heatmap component — Chinese UI."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from database.queries import get_hourly_flow_patterns


# Trading session zones (UTC hours)
SESSIONS = [
    {"name": "亚洲时段", "x0": 0, "x1": 9, "color": "#3b82f6"},
    {"name": "欧洲时段", "x0": 7, "x1": 16, "color": "#22c55e"},
    {"name": "美国时段", "x0": 13, "x1": 22, "color": "#f97316"},
]


def render_hourly_heatmap():
    st.subheader("⏰ 时间规律分析")

    sel_chain = st.session_state.get("selected_chain", "all")
    chain = None if sel_chain == "all" else sel_chain
    token_filter = st.session_state.get("selected_token", "ALL")

    col1, _ = st.columns([2, 3])
    with col1:
        period = st.selectbox(
            "分析周期",
            options=[7, 30],
            format_func=lambda x: f"最近 {x} 天",
            key="heatmap_period",
        )

    data = get_hourly_flow_patterns(days=period, chain=chain, token_filter=token_filter)

    df = pd.DataFrame(data)
    df["net_flow"] = df["avg_outflow"] - df["avg_inflow"]
    df["hour_label"] = [f"{h:02d}:00" for h in df["hour"]]

    fig = go.Figure()

    # Bars: avg inflow / outflow
    fig.add_trace(go.Bar(
        x=df["hour_label"], y=df["avg_inflow"],
        name="平均流入",
        marker_color="#ef4444",
        hovertemplate="%{y:$,.0f}<extra>平均流入</extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["hour_label"], y=df["avg_outflow"],
        name="平均流出",
        marker_color="#22c55e",
        hovertemplate="%{y:$,.0f}<extra>平均流出</extra>",
    ))

    # Net flow line
    fig.add_trace(go.Scatter(
        x=df["hour_label"], y=df["net_flow"],
        name="净流量",
        mode="lines+markers",
        line=dict(color="#fbbf24", width=2),
        marker=dict(color=np.where(df["net_flow"] >= 0, "#22c55e", "#ef4444"), size=6),
        yaxis="y2",
        hovertemplate="%{y:$,.0f}<extra>净流量</extra>",
    ))

    # Trading session overlays
    for sess in SESSIONS:
        fig.add_vrect(
            x0=sess["x0"] - 0.5, x1=sess["x1"] - 0.5,
            fillcolor=sess["color"], opacity=0.08,
            line_width=0,
            annotation_text=sess["name"],
            annotation_position="top left",
        )

    fig.add_hline(y=0, line_dash="dot", line_color="#6b7280", opacity=0.4, yref="y2")

    fig.update_layout(
        title=f"每小时平均交易所流量 (最近 {period} 天, UTC)",
        barmode="group",
        margin=dict(l=0, r=0, t=30, b=0),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(title="UTC 小时", dtick=2),
        yaxis=dict(title="平均流量 (USD)"),
        yaxis2=dict(
            title="净流量 (USD)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Peak hour insight
    peak = df.loc[df["net_flow"].abs().idxmax()]
    peak_dir = "净流出" if peak["net_flow"] > 0 else "净流入"
    st.caption(
        f"📊 {period}天统计: {peak['hour_label']} UTC 是资金最活跃时段 "
        f"({peak_dir} {abs(peak['net_flow']):,.0f} USD/天)。"
        f"亚洲(蓝) · 欧洲(绿) · 美国(橙) 时段重叠标注。"
    )
