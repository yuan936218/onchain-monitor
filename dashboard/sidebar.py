"""Dashboard sidebar component — Chinese UI."""

import streamlit as st
from config.settings import (
    THRESHOLD_LARGE_TRANSFER, THRESHOLD_EXCHANGE_INFLOW,
    THRESHOLD_WHALE_MOVE, DEFAULT_POLL_INTERVAL_SECONDS,
    DATA_RETENTION_DAYS,
)


def render_sidebar():
    with st.sidebar:
        st.header("⚙️ 设置")

        # API Keys section
        st.subheader("🔑 API密钥")
        etherscan_key = st.text_input(
            "Etherscan API Key",
            type="password",
            value=st.session_state.get("etherscan_key", ""),
            help="在 https://etherscan.io/register 免费申请",
        )
        if etherscan_key != st.session_state.get("etherscan_key", ""):
            st.session_state["etherscan_key"] = etherscan_key
            import os
            os.environ["ETHERSCAN_API_KEY"] = etherscan_key

        feishu_url = st.text_input(
            "飞书 Webhook URL",
            type="password",
            value=st.session_state.get("feishu_webhook", ""),
            help="在飞书群 → 设置 → 群机器人 → 添加机器人 → 复制 Webhook 地址",
        )
        if feishu_url != st.session_state.get("feishu_webhook", ""):
            st.session_state["feishu_webhook"] = feishu_url
            import os
            os.environ["FEISHU_WEBHOOK_URL"] = feishu_url

        # Thresholds
        st.subheader("⚡ 警报阈值")
        threshold_large = st.number_input(
            "大额转账阈值 (USD)",
            min_value=100_000,
            max_value=100_000_000,
            value=int(st.session_state.get("threshold_large", THRESHOLD_LARGE_TRANSFER)),
            step=100_000,
            format="%d",
        )
        st.session_state["threshold_large"] = threshold_large

        threshold_inflow = st.number_input(
            "交易所单笔流入阈值 (USD)",
            min_value=500_000,
            max_value=100_000_000,
            value=int(st.session_state.get("threshold_inflow", THRESHOLD_EXCHANGE_INFLOW)),
            step=500_000,
            format="%d",
        )
        st.session_state["threshold_inflow"] = threshold_inflow

        # Poll interval
        st.subheader("🔄 数据采集")
        poll_interval = st.selectbox(
            "轮询间隔",
            options=[30, 60, 120, 300],
            index=2,
            format_func=lambda x: f"{x} 秒",
        )
        st.session_state["poll_interval"] = poll_interval

        running = st.session_state.get("collector_running", False)
        if st.button("🟢 开始采集" if not running else "🔴 停止采集"):
            st.session_state["collector_running"] = not running
            st.rerun()

        status_text = "🟢 运行中" if running else "⏸️ 已暂停"
        st.caption(f"采集器: {status_text}")

        # Data retention
        st.subheader("📊 数据保留")
        retention_days = st.selectbox(
            "保留数据",
            options=[7, 30, 90, 180],
            index=2,
            format_func=lambda x: f"{x} 天",
        )
        st.session_state["retention_days"] = retention_days

        st.divider()
        if st.button("🔄 立即刷新"):
            st.session_state["force_refresh"] = True
            st.rerun()

        st.caption(f"链上监控 v1.0")
