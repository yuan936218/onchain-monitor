"""Market intelligence brief — natural language insights from on-chain data."""

from __future__ import annotations

import streamlit as st
from utils.formatters import format_usd


def render_market_intel():
    from database.queries import get_market_intel_data

    st.subheader("🧠 市场情报摘要")

    sel_chain = st.session_state.get("selected_chain", "all")
    chain = None if sel_chain == "all" else sel_chain

    col1, _ = st.columns([2, 3])
    with col1:
        window = st.selectbox(
            "分析窗口",
            options=[1, 3, 6, 12],
            index=2,
            format_func=lambda x: f"最近 {x} 小时",
            key="intel_window",
        )

    data = get_market_intel_data(hours=window, chain=chain)

    if data["total_transfers"] == 0:
        st.info("📡 暂无足够数据生成市场情报。采集器运行后会自动分析。")
        return

    # Build intelligence bullets
    bullets = []

    # 1. Net flow direction
    net = data["net_flow"]
    if abs(net) > 1_000_000:
        direction = "流出交易所" if net > 0 else "流入交易所"
        signal = "🟢 看涨信号" if net > 0 else "🔴 看跌信号"
        bullets.append({
            "icon": "📊",
            "title": f"资金{direction} | {signal}",
            "body": (
                f"最近{data['hours']}小时，{format_usd(data['total_outflow'])} 流出，"
                f"{format_usd(data['total_inflow'])} 流入，"
                f"净{'流出' if net > 0 else '流入'} {format_usd(abs(net))}。"
                f"{'大户正在将资产从交易所提走，可能是在囤币或转入冷钱包。' if net > 0 else '大量资金进入交易所，通常预示短期抛售压力增加。'}"
            ),
            "severity": "bullish" if net > 0 else "bearish",
        })
    else:
        bullets.append({
            "icon": "📊",
            "title": "资金流向平衡",
            "body": f"最近{data['hours']}小时交易所资金流向基本平衡，净流量 {format_usd(abs(net))}，市场情绪中性。",
            "severity": "neutral",
        })

    # 2. Large transfers
    if data["large_count"] > 0:
        bullets.append({
            "icon": "💸",
            "title": f"检测到 {data['large_count']} 笔超大额转账 (>$10M)",
            "body": "超大额转账通常与机构调仓、OTC交易或交易所冷热钱包互转有关。建议关注这些地址的后续动向。",
            "severity": "warning",
        })

    # 3. Whale activity
    if data["whale_moves"]:
        whale = data["whale_moves"][0]
        whale_dir = "→ 交易所" if whale["to_label"] else ("交易所 →" if whale["from_label"] else "链上转账")
        bullets.append({
            "icon": "🐋",
            "title": f"巨鲸活动: {format_usd(whale['value_usd'])} {whale['asset']}",
            "body": (
                f"最大单笔: {whale['from_label'] or '未知'} → {whale['to_label'] or '未知'} "
                f"({whale_dir})。"
                f"{'巨鲸向交易所转入大额资产，密切关注是否出现抛售。' if whale['to_label'] else '巨鲸从交易所提走资产，可能是长期持有的看涨信号。'}"
            ),
            "severity": "critical" if whale["to_label"] else "bullish",
        })

    # 4. Mint/burn
    net_mint = data["net_mint"]
    if abs(net_mint) > 1_000_000:
        action = "铸造" if net_mint > 0 else "销毁"
        bullets.append({
            "icon": "🏦",
            "title": f"稳定币净{action}: {format_usd(abs(net_mint))}",
            "body": (
                f"新{action} {format_usd(abs(net_mint))} 稳定币。"
                f"{'稳定币供应量增加通常利好市场流动性。' if net_mint > 0 else '稳定币供应量减少可能反映市场去杠杆或资金外流。'}"
            ),
            "severity": "bullish" if net_mint > 0 else "bearish",
        })

    # 5. Exchange balance changes
    if data["balance_signals"]:
        sig = data["balance_signals"][0]
        direction = "增加" if sig["change"] > 0 else "减少"
        bullets.append({
            "icon": "🏛️",
            "title": f"{sig['exchange']} 余额{direction}: {format_usd(abs(sig['change']))}",
            "body": (
                f"当前余额 {format_usd(sig['current'])}，"
                f"最近{data['hours']}小时{direction} {format_usd(abs(sig['change']))}。"
                f"{'交易所余额增加 = 用户充值 = 潜在抛售。' if sig['change'] > 0 else '交易所余额减少 = 用户提币 = 囤币看涨信号。'}"
            ),
            "severity": "bearish" if sig["change"] > 0 else "bullish",
        })

    # Render bullets as styled cards
    severity_colors = {
        "bullish": "#22c55e",
        "bearish": "#ef4444",
        "warning": "#f59e0b",
        "neutral": "#6b7280",
        "critical": "#ef4444",
    }

    cols = st.columns(min(len(bullets), 2))
    for i, bullet in enumerate(bullets):
        color = severity_colors.get(bullet["severity"], "#6b7280")
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### {bullet['icon']} {bullet['title']}")
                st.caption(bullet["body"])
