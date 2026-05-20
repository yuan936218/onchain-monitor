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

        if st.button("🧪 测试 API Key", help="验证 Etherscan API Key 是否有效"):
            if etherscan_key:
                import httpx, time
                from collectors.base import make_client
                try:
                    client = make_client(timeout=15)
                    resp = client.get("https://api.etherscan.io/v2/api", params={
                        "chainid": "1",
                        "module": "account",
                        "action": "txlist",
                        "address": "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",
                        "startblock": 0,
                        "endblock": 99999999,
                        "page": 1,
                        "offset": 1,
                        "sort": "desc",
                        "apikey": etherscan_key,
                    })
                    data = resp.json()
                    if data.get("status") == "1" and isinstance(data.get("result"), list):
                        block = int(data["result"][0]["blockNumber"]) if data["result"] else 0
                        st.success(f"✅ API Key 有效！最新交易区块: {block:,}")
                    elif data.get("message") == "NOTOK":
                        st.error(f"❌ API Key 无效: {data.get('result', '请检查Key是否正确')}")
                    elif data.get("result") and isinstance(data["result"], str):
                        st.warning(f"⚠️ 返回: {data['result'][:200]}")
                    else:
                        st.error(f"❌ API 返回: {data.get('message', str(data)[:200])}")
                except Exception as e:
                    st.error(f"❌ 连接失败: {str(e)[:200]}")
            else:
                st.warning("请先输入 API Key")

        if st.button("🔬 诊断采集端点", help="测试 Tokentx 端点 (采集器实际使用的API)"):
            if etherscan_key:
                import httpx
                from collectors.base import make_client
                try:
                    client = make_client(timeout=15)
                    # Test tokentx on Binance wallet — the endpoint the collector uses
                    resp = client.get("https://api.etherscan.io/v2/api", params={
                        "chainid": "1",
                        "module": "account",
                        "action": "tokentx",
                        "contractaddress": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
                        "address": "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",  # Binance wallet
                        "startblock": 0,
                        "endblock": 99999999,
                        "page": 1,
                        "offset": 3,
                        "sort": "desc",
                        "apikey": etherscan_key,
                    })
                    data = resp.json()
                    st.caption(f"请求: tokentx USDT @ Binance (最新3笔)")
                    status = data.get("status")
                    result = data.get("result")
                    msg = data.get("message", "")
                    if status == "1" and isinstance(result, list):
                        latest_block = int(result[0]["blockNumber"]) if result else 0
                        st.success(f"✅ Tokentx端点正常！最新 {len(result)} 笔, 区块 {latest_block:,}")
                        for tx in result[:2]:
                            st.caption(f"TX: {tx.get('hash','?')[:16]}... 金额: {float(tx.get('value',0))/1e6:.2f} {tx.get('tokenSymbol','?')} @ 区块 {tx.get('blockNumber','?')}")
                    elif status == "0" and isinstance(result, list):
                        st.warning(f"⚠️ Status=0 但返回列表: {len(result)} 条. 消息: {msg[:100]}")
                    elif "No transactions" in msg or "No records" in msg:
                        st.warning(f"⚠️ 该区块范围无交易. 消息: {msg[:100]}")
                    else:
                        st.error(f"❌ Tokentx失败: status={status}, msg={msg[:200]}, result={str(result)[:200]}")
                except Exception as e:
                    st.error(f"❌ 连接失败: {str(e)[:200]}")
            else:
                st.warning("请先输入 API Key")

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
            min_value=1_000_000,
            max_value=100_000_000,
            value=int(st.session_state.get("threshold_large", THRESHOLD_LARGE_TRANSFER)),
            step=1_000_000,
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
