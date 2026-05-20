"""Exchange flow bar chart component — Chinese UI."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from database.queries import get_exchange_flow_timeseries_by_exchange


def _build_flow_chart(df, title):
    """Build a Plotly figure: inflow/outflow grouped bars + net flow line."""
    fig = go.Figure()

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
    fig.add_trace(go.Scatter(
        x=df["hour"], y=df["net_flow"],
        name="净流量",
        mode="lines+markers",
        line=dict(color="#fbbf24", width=2),
        marker=dict(color=np.where(df["net_flow"] >= 0, "#22c55e", "#ef4444"), size=6),
        yaxis="y2",
        hovertemplate="%{y:$,.0f}<extra>净流量</extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="#6b7280", opacity=0.4, yref="y2")

    fig.update_layout(
        title=title,
        barmode="group",
        margin=dict(l=0, r=0, t=30, b=0),
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

    return fig


def render_exchange_flow_chart():
    st.subheader("📈 交易所资金流向 (按小时)")

    sel_chain = st.session_state.get("selected_chain", "all")
    chain = None if sel_chain == "all" else sel_chain
    token_filter = st.session_state.get("selected_token", "ALL")

    per_exchange = get_exchange_flow_timeseries_by_exchange(hours=24, chain=chain, token_filter=token_filter)

    if not per_exchange:
        st.caption("暂无交易所流量数据，请先启动采集器。")
        return

    # Build combined DataFrame (sum across all exchanges per hour)
    combined = {}
    for name, entries in per_exchange.items():
        for e in entries:
            h = e["hour"]
            if h not in combined:
                combined[h] = {"inflow": 0, "outflow": 0}
            combined[h]["inflow"] += e["inflow"]
            combined[h]["outflow"] += e["outflow"]
    combined_df = pd.DataFrame([
        {"hour": h, "inflow": v["inflow"], "outflow": v["outflow"],
         "net_flow": v["outflow"] - v["inflow"]}
        for h, v in sorted(combined.items())
    ])

    # Selectbox for exchange filter
    exchange_names = sorted(per_exchange.keys())
    selected = st.selectbox(
        "选择交易所",
        ["全部交易所"] + exchange_names,
        key="exchange_flow_select",
    )

    if selected == "全部交易所":
        df = combined_df
        title = "全部交易所 资金流向"
        prefix = ""
    else:
        entries = per_exchange[selected]
        df = pd.DataFrame(entries)
        title = f"{selected} 资金流向"
        prefix = f"{selected} "

    # Summary insight
    total_net = df["net_flow"].sum()
    abs_net = abs(total_net)
    if total_net > 0:
        st.caption(f"📊 {prefix}24h 净流出 {abs_net:,.0f} USD → 资金倾向流出交易所（囤币信号）")
    elif total_net < 0:
        st.caption(f"📊 {prefix}24h 净流入 {abs_net:,.0f} USD → 资金倾向流入交易所（潜在抛压）")
    else:
        st.caption(f"📊 {prefix}24h 净流量 0 USD → 交易所资金流向平衡")

    fig = _build_flow_chart(df, title)
    st.plotly_chart(fig, use_container_width=True)
