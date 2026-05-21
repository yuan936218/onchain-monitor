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

        # ── Chain selector ──
        chain_options = {"all": "全部链", "ethereum": "Ethereum", "arbitrum": "Arbitrum", "bsc": "BSC"}
        selected_chain = st.selectbox(
            "⛓️ 监控链",
            options=list(chain_options.keys()),
            format_func=lambda x: chain_options[x],
            key="selected_chain",
        )

        # ── Token filter ──
        st.subheader("🪙 监控币种")
        token_filter = st.selectbox(
            "币种筛选",
            options=["ALL", "USDT", "USDC", "ETH", "WBTC"],
            format_func=lambda x: "全部币种" if x == "ALL" else x,
            key="selected_token",
        )

        st.divider()

        # ── Status indicator ──
        running = st.session_state.get("collector_running", True)
        st.caption(f"采集状态: {'🟢 运行中' if running else '⏸️ 已暂停'}")

        if st.button("⏸️ 暂停采集" if running else "▶️ 恢复采集"):
            st.session_state["collector_running"] = not running
            st.rerun()

        st.divider()

        # ── API Keys ──
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

        col_test1, col_test2 = st.columns(2)
        with col_test1:
            if st.button("🧪 测试", help="验证 API Key 是否有效"):
                if etherscan_key:
                    import httpx
                    from collectors.base import make_client
                    try:
                        client = make_client(timeout=15)
                        resp = client.get("https://api.etherscan.io/v2/api", params={
                            "chainid": "1", "module": "account", "action": "txlist",
                            "address": "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",
                            "startblock": 0, "endblock": 99999999,
                            "page": 1, "offset": 1, "sort": "desc",
                            "apikey": etherscan_key,
                        })
                        data = resp.json()
                        if data.get("status") == "1" and isinstance(data.get("result"), list):
                            block = int(data["result"][0]["blockNumber"]) if data["result"] else 0
                            st.success(f"✅ 区块 {block:,}")
                        elif data.get("message") == "NOTOK":
                            st.error("❌ 无效")
                        else:
                            st.error(f"❌ {str(data.get('message', ''))[:60]}")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:60]}")
                else:
                    st.warning("请先输入 Key")
        with col_test2:
            if st.button("🔬 诊断", help="测试采集器实际使用的 tokentx 端点"):
                if etherscan_key:
                    import httpx
                    from collectors.base import make_client
                    try:
                        client = make_client(timeout=15)
                        resp = client.get("https://api.etherscan.io/v2/api", params={
                            "chainid": "1", "module": "account", "action": "tokentx",
                            "contractaddress": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                            "address": "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",
                            "startblock": 0, "endblock": 99999999,
                            "page": 1, "offset": 3, "sort": "desc",
                            "apikey": etherscan_key,
                        })
                        data = resp.json()
                        if data.get("status") == "1" and isinstance(data.get("result"), list):
                            st.success(f"✅ {len(data['result'])} 笔")
                        else:
                            st.error(f"❌ {str(data.get('message', ''))[:60]}")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:60]}")
                else:
                    st.warning("请先输入 Key")

        feishu_url = st.text_input(
            "飞书 Webhook URL",
            type="password",
            value=st.session_state.get("feishu_webhook", ""),
            help="飞书群 → 设置 → 群机器人 → 添加机器人 → 复制 Webhook 地址",
        )
        if feishu_url != st.session_state.get("feishu_webhook", ""):
            st.session_state["feishu_webhook"] = feishu_url
            import os
            os.environ["FEISHU_WEBHOOK_URL"] = feishu_url

        st.divider()

        # ── Alert Thresholds ──
        st.subheader("⚡ 警报阈值")
        threshold_large = st.number_input(
            "大额转账阈值 (USD)",
            min_value=1_000_000, max_value=100_000_000,
            value=int(st.session_state.get("threshold_large", THRESHOLD_LARGE_TRANSFER)),
            step=1_000_000, format="%d",
        )
        st.session_state["threshold_large"] = threshold_large

        threshold_inflow = st.number_input(
            "交易所单笔流入阈值 (USD)",
            min_value=500_000, max_value=100_000_000,
            value=int(st.session_state.get("threshold_inflow", THRESHOLD_EXCHANGE_INFLOW)),
            step=500_000, format="%d",
        )
        st.session_state["threshold_inflow"] = threshold_inflow

        st.divider()

        # ── Collection Settings ──
        st.subheader("🔄 数据采集")
        poll_interval = st.selectbox(
            "轮询间隔",
            options=[30, 60, 120, 300],
            index=2, format_func=lambda x: f"{x} 秒",
        )
        st.session_state["poll_interval"] = poll_interval

        retention_days = st.selectbox(
            "数据保留",
            options=[7, 30, 90, 180],
            index=2, format_func=lambda x: f"{x} 天",
        )
        st.session_state["retention_days"] = retention_days

        st.divider()

        # ── API Key setup hint ──
        api_key_set = bool(st.session_state.get("etherscan_key", ""))
        if not api_key_set:
            st.info(
                "💡 **API Key 未持久化**\n\n"
                "面板休眠后 Key 会丢失。建议在 Streamlit Cloud 管理页 → **Settings → Secrets** 中设置：\n"
                '```\nETHERSCAN_API_KEY = "你的key"\n```'
            )

        if st.button("🔄 立即刷新面板"):
            st.session_state["force_refresh"] = True
            st.rerun()

        st.caption("链上监控 v2.0 · 启动自动追补 · 使用中持续采集")
